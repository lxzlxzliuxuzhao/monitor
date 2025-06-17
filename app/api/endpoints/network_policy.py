from fastapi import APIRouter, HTTPException, status
from app.services.network_policy import NetworkPolicyService as network_policy_service
from app.models.schemas import DeploymentNetworkPolicyCreate, DeploymentNetworkPolicyResponse, NetworkPolicyRuleResponse
from kubernetes import client

router = APIRouter()

@router.post(
    "/network-policies/deployment",
    response_model=DeploymentNetworkPolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="为Deployment创建网络策略"
)
async def create_deployment_network_policy(
    request: DeploymentNetworkPolicyCreate
) -> DeploymentNetworkPolicyResponse:
    """为指定Deployment创建网络策略
    
    此接口为Kubernetes Deployment管理的所有Pod创建网络策略
    
    参数:
        - deployment_name: Deployment名称
        - namespace: 命名空间 (默认为'default')
        - rules: 网络策略规则列表
        
    响应:
        - policy_name: 创建的策略名称
        - deployment_name: 关联的Deployment名称
        - namespace: 命名空间
        - pod_selector: 应用的Pod选择器标签
    """
    try:
        # 创建服务实例
        service = network_policy_service()
        
        # 创建策略
        return service.create_deployment_policy(request)
        
    except ValueError as e:
        # 业务逻辑错误返回400
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # 其他错误返回500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务内部错误: {str(e)}"
        )

@router.get(
    "/network-policies/deployment/{deployment_name}",
    response_model=DeploymentNetworkPolicyResponse,
    summary="获取Deployment的网络策略"
)
async def get_deployment_network_policy(
    deployment_name: str, 
    namespace: str = "default"
) -> DeploymentNetworkPolicyResponse:
    """获取指定Deployment的网络策略信息"""
    try:
        service = network_policy_service()

        # 生成策略名前缀，统一格式
        policy_name_prefix = f"np-{deployment_name[:45]}-policy".lower().replace("_", "-")[:63]

        # 获取所有策略（不加 label_selector 以确保能获取所有）
        policies = service.networking_v1.list_namespaced_network_policy(
            namespace=namespace
        ).items

        # 筛选策略名匹配的
        matching_policies = [
            p for p in policies 
            if p.metadata.name.startswith(policy_name_prefix)
        ]

        if not matching_policies:
            raise HTTPException(
                status_code=404, 
                detail=f"未找到 {deployment_name} 的网络策略"
            )

        policy = matching_policies[0]

        # 解析 ingress 规则
        ingress_rules = [
            NetworkPolicyRuleResponse(
                direction="ingress",
                protocol=port.protocol,
                ports=[port.port],
                source_pod_labels=peer.pod_selector.match_labels if peer.pod_selector else None,
                source_namespace_labels=peer.namespace_selector.match_labels if peer.namespace_selector else None
            )
            for rule in policy.spec.ingress or []
            for peer in rule._from or []
            for port in rule.ports or [client.V1NetworkPolicyPort(protocol="TCP")]
        ]

        # 解析 egress 规则
        egress_rules = [
            NetworkPolicyRuleResponse(
                direction="egress",
                protocol=port.protocol,
                ports=[port.port],
                source_pod_labels=None,
                source_namespace_labels=None
            )
            for rule in policy.spec.egress or []
            for port in rule.ports or [client.V1NetworkPolicyPort(protocol="TCP")]
        ]

        return DeploymentNetworkPolicyResponse(
            policy_name=policy.metadata.name,
            deployment_name=deployment_name,
            namespace=namespace,
            pod_selector=policy.spec.pod_selector.match_labels,
            ingress_rules=ingress_rules,
            egress_rules=egress_rules
        )

    except client.exceptions.ApiException as e:
        raise HTTPException(
            status_code=e.status,
            detail=f"查询失败: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"查询失败: {str(e)}"
        )
    