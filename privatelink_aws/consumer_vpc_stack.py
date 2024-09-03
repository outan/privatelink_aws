from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
)
from constructs import Construct

class ConsumerVpcStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, provider_endpoint_service: ec2.VpcEndpointService, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # VPC作成
        self.vpc = ec2.Vpc(self, "ConsumerVPC",
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    name="Private",
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

        self.endpoint_sg = ec2.SecurityGroup(self, "EndpointSecurityGroup",
            vpc=self.vpc,
            description="Security group for VPC Endpoint",
            allow_all_outbound=True
        )
        vpc_cidr = self.vpc.vpc_cidr_block
        self.endpoint_sg.add_ingress_rule(
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
        self.ec2_instance = ec2.Instance(self, "ConsumerInstance",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            machine_image=ec2.AmazonLinuxImage(generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_group=self.ssm_sg,
            role=self.ec2_role
        )

        # VPCエンドポイント作成
        self.vpc_endpoint = ec2.InterfaceVpcEndpoint(self, "ServiceVpcEndpoint",
            vpc=self.vpc,
            service=ec2.InterfaceVpcEndpointService(provider_endpoint_service.vpc_endpoint_service_name),
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            private_dns_enabled=True,
            security_groups=[self.endpoint_sg]
        )
