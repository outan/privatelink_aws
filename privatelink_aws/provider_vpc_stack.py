from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_elasticloadbalancingv2_targets as targets
)
from constructs import Construct

class ProviderVpcStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # VPC作成
        self.vpc = ec2.Vpc(self, "ProviderVPC",
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24
                )
            ],
            nat_gateways=0
        )

        # SSM接続用のVPCエンドポイントを作成
        self.vpc.add_interface_endpoint("SSMEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SSM
        )
        self.vpc.add_interface_endpoint("SSMMessagesEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES
        )
        self.vpc.add_interface_endpoint("EC2MessagesEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.EC2_MESSAGES
        )

        # セキュリティグループ作成
        self.ssm_sg = ec2.SecurityGroup(self, "SSMSecurityGroup",
            vpc=self.vpc,
            description="Security group for SSM connections",
            allow_all_outbound=True
        )

        self.web_sg = ec2.SecurityGroup(self, "WebSecurityGroup",
            vpc=self.vpc,
            description="Security group for web traffic",
            allow_all_outbound=True
        )
        vpc_cidr = self.vpc.vpc_cidr_block
        self.web_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc_cidr),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP traffic from within the VPC"
        )

        # IAMロール作成
        self.ec2_role = iam.Role(self, "EC2SSMRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
            ]
        )

        # EC2インスタンス作成
        self.ec2_instance = ec2.Instance(self, "WebServer",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            machine_image=ec2.AmazonLinuxImage(generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_group=self.web_sg,
            role=self.ec2_role
        )

        # ユーザーデータスクリプトの追加
        self.ec2_instance.add_user_data(
            "yum update -y",
            "yum install -y httpd",
            "echo '<html><body><h1>Hello from Provider VPC!</h1></body></html>' > /var/www/html/index.html",
            "systemctl start httpd",
            "systemctl enable httpd"
        )

        # NLB作成
        self.nlb = elbv2.NetworkLoadBalancer(self, "NLB",
            vpc=self.vpc,
            internet_facing=False,
            cross_zone_enabled=True
        )

        # ターゲットグループ作成
        self.target_group = elbv2.NetworkTargetGroup(self, "TargetGroup",
            vpc=self.vpc,
            port=80,
            protocol=elbv2.Protocol.TCP,
            target_type=elbv2.TargetType.INSTANCE,
            health_check=elbv2.HealthCheck(
                protocol=elbv2.Protocol.HTTP
            )
        )
        self.target_group.add_target(targets.InstanceTarget(self.ec2_instance))

        # リスナー作成
        self.nlb.add_listener("Listener",
            port=80,
            protocol=elbv2.Protocol.TCP,
            default_target_groups=[self.target_group]
        )

        # VPCエンドポイントサービス作成
        self.endpoint_service = ec2.VpcEndpointService(self, "EndpointService",
            vpc_endpoint_service_load_balancers=[self.nlb],
            acceptance_required=False,
            allowed_principals=[iam.ArnPrincipal(self.ec2_role.role_arn)]
        )
