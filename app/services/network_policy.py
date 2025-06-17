from kubernetes import client, config
from kubernetes.client.rest import ApiException
from app.core.config import settings
from app.models import schemas
from typing import Dict

class NetworkPolicyService:
    """Kubernetes网络策略管理服务
    
    提供为Deployment创建网络策略的功能
    """
    
    def __init__(self):
        """初始化Kubernetes客户端"""
        self._init_k8s_client()
        
    def _init_k8s_client(self) -> None:
        """配置Kubernetes客户端连接
        
        根据配置决定使用集群内配置还是本地kubeconfig
        
        异常:
            RuntimeError: 当Kubernetes配置加载失败时抛出
        """
        try:
            config.load_incluster_config()  # 集群内运行
        except config.ConfigException:
            config.load_kube_config()  # 集群外运行

        # 初始化API客户端
        self.core_v1 = client.CoreV1Api()
        self.networking_v1 = client.NetworkingV1Api()
        self.apps_v1 = client.AppsV1Api()

    def get_deployment(self, name: str, namespace: str) -> client.V1Deployment:
        """获取指定Deployment信息
        
        参数:
            name: Deployment名称
            namespace: 命名空间
            
        返回:
            V1Deployment对象
            
        异常:
            ValueError: 当Deployment不存在或API调用失败
        """
        try:
            return self.apps_v1.read_namespaced_deployment(name, namespace)
        except ApiException as e:
            if e.status == 404:
                raise ValueError(f"命名空间 '{namespace}' 中找不到Deployment '{name}'")
            raise ValueError(f"Kubernetes API错误: {e.reason}")
    
    def create_network_policy(
        self, 
        namespace: str, 
        policy_body: client.V1NetworkPolicy
    ) -> client.V1NetworkPolicy:
        """创建网络策略
        
        参数:
            namespace: 目标命名空间
            policy_body: NetworkPolicy定义
            
        返回:
            创建的V1NetworkPolicy对象
            
        异常:
            ValueError: 当策略创建失败
        """
        try:
            return self.networking_v1.create_namespaced_network_policy(
                namespace=namespace,
                body=policy_body
            )
        except ApiException as e:
            raise ValueError(f"网络策略创建失败: {e.reason}")
    
    def create_deployment_policy(
        self,
        request: schemas.DeploymentNetworkPolicyCreate
    ) -> schemas.DeploymentNetworkPolicyResponse:
        """为Deployment创建网络策略
        
        策略基于Deployment的Pod选择器创建，无需修改现有Pod标签
        
        参数:
            request: 策略创建请求参数
            
        返回:
            创建结果响应
            
        异常:
            ValueError: 当任何操作步骤失败
        """
        # 1. 验证Deployment是否存在
        deployment = self.get_deployment(request.deployment_name, request.namespace)
        
        # 2. 提取Deployment的Pod选择器标签
        pod_selector = deployment.spec.selector.match_labels
        
        # 3. 创建网络策略
        policy = self._build_network_policy(request, pod_selector)
        created_policy = self.create_network_policy(request.namespace, policy)
        
        return schemas.DeploymentNetworkPolicyResponse(
            policy_name=created_policy.metadata.name,
            deployment_name=request.deployment_name,
            namespace=request.namespace,
            pod_selector=pod_selector,
            ingress_rules=[
                self._convert_to_response_rule(rule) 
                for rule in request.rules if rule.direction == "ingress"
            ],
            egress_rules=[
                self._convert_to_response_rule(rule) 
                for rule in request.rules if rule.direction == "egress"
            ]
        )
    
    def _build_network_policy(
        self,
        request: schemas.DeploymentNetworkPolicyCreate,
        pod_selector: Dict[str, str]
    ) -> client.V1NetworkPolicy:
        """构建Kubernetes NetworkPolicy对象
        
        参数:
            request: 策略创建请求
            pod_selector: Pod选择器标签
            
        返回:
            完整的V1NetworkPolicy对象
        """
        # 构建入站规则
        ingress_rules = [
            self._build_ingress_rule(rule) 
            for rule in request.rules 
            if rule.direction == "ingress"
        ]
        
        # 构建出站规则
        egress_rules = [
            self._build_egress_rule(rule) 
            for rule in request.rules 
            if rule.direction == "egress"
        ]
        
        # 生成策略名称 (Kubernetes名称限制63字符)
        policy_name = f"np-{request.deployment_name[:45]}-policy".lower().replace("_", "-")[:63]
        
        return client.V1NetworkPolicy(
            api_version="networking.k8s.io/v1",
            kind="NetworkPolicy",
            metadata=client.V1ObjectMeta(name=policy_name),
            spec=client.V1NetworkPolicySpec(
                pod_selector=client.V1LabelSelector(match_labels=pod_selector),
                ingress=ingress_rules,
                egress=egress_rules,
                policy_types=["Ingress", "Egress"]
            )
        )
    
    def _build_ingress_rule(
        self,
        rule: schemas.NetworkPolicyRule
    ) -> client.V1NetworkPolicyIngressRule:
        """构建入站规则
        
        参数:
            rule: 规则定义
            
        返回:
            完整的V1NetworkPolicyIngressRule对象
        """
        peers = []
        
        # 添加基于Pod标签的源选择器
        if rule.source_pod_labels:
            peers.append(client.V1NetworkPolicyPeer(
                pod_selector=client.V1LabelSelector(
                    match_labels=rule.source_pod_labels
                )
            ))
        
        # 添加基于命名空间的源选择器
        if rule.source_namespace_labels:
            peers.append(client.V1NetworkPolicyPeer(
                namespace_selector=client.V1LabelSelector(
                    match_labels=rule.source_namespace_labels
                )
            ))
        
        # 构建端口规则
        ports = [
            client.V1NetworkPolicyPort(port=p, protocol=rule.protocol.upper()) 
            for p in rule.ports
        ]
        
        return client.V1NetworkPolicyIngressRule(
            _from=peers if peers else None,
            ports=ports
        )
    
    def _build_egress_rule(
        self,
        rule: schemas.NetworkPolicyRule
    ) -> client.V1NetworkPolicyEgressRule:
        """构建出站规则 (简化实现)
        
        注意: 实际应用中需要完善此方法
        
        参数:
            rule: 规则定义
            
        返回:
            简化的V1NetworkPolicyEgressRule对象
        """
        # 此处仅实现端口规则，实际应用中需添加目标选择器
        ports = [
            client.V1NetworkPolicyPort(port=p, protocol=rule.protocol.upper()) 
            for p in rule.ports
        ]
        return client.V1NetworkPolicyEgressRule(ports=ports)
    
    def _convert_to_response_rule(
        self,
        rule: schemas.NetworkPolicyRule
    ) -> schemas.NetworkPolicyRuleResponse:
        """将请求规则转换为响应规则对象"""
        return schemas.NetworkPolicyRuleResponse(
            direction=rule.direction,
            protocol=rule.protocol,
            ports=rule.ports,
            source_pod_labels=rule.source_pod_labels,
            source_namespace_labels=rule.source_namespace_labels,
            description=rule.description
        )