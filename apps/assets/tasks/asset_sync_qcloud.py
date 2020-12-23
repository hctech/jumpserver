#!/usr/bin/env python
# coding: utf-8
# Author: huangchao

from assets.models import Asset, AdminUser, Node
from assets.api.qcloud import QcloudCVMApi, QcloudVpcApi
from celery import shared_task
from ops.celery.decorator import after_app_ready_start
from ops.celery.utils import (
    create_or_update_celery_periodic_tasks, disable_celery_periodic_task
)
from common.utils import get_logger

logger = get_logger(__file__)

def get_os_adminuser(osname):
    """更新osname获取跳板机管理用户"""
    if "CentOS" in osname:
        adminuser_name = "qcloud_root_qiexr"
    elif "Ubuntu" in osname:
        adminuser_name = "qcloud_ubuntu_qiexr"
    else:
        adminuser_name = "default"
    return AdminUser.objects.filter(name=adminuser_name)[0] \
        if AdminUser.objects.filter(name=adminuser_name)[0] \
        else None

def delete_asset(ip):
    """删除资产"""
    return Asset.objects.filter(ip=ip).delete()

def query_asset_by_hostname(hostname):
    """根据主机名查询资产"""
    return Asset.objects.filter(hostname=hostname)

def query_asset_by_ip(ip):
    """根据IP查询资产"""
    return Asset.objects.filter(ip=ip)

def update_asset_hostname_by_ip(ip, hostname):
    """根据IP更新主机名"""
    return Asset.objects.filter(ip=ip).update(hostname=hostname)

def create_or_update_qcloud_node():
    """创建或更新腾讯云Node节点"""
    return Node.default_node().get_or_create_child("腾讯云")[0]

def create_or_update_vpc_node(vpc_name):
    """创建或更新VPC Node节点"""
    qcloud_node = create_or_update_qcloud_node()
    return qcloud_node.get_or_create_child("vpc_name")[0]

def create_or_update_vpc_subnet_node(vpc_name, subnet_name):
    """创建或更新VPC子网Node"""
    vpc_node = create_or_update_vpc_node(vpc_name)
    return vpc_node.get_or_create_child(subnet_name)[0]

def create_or_update_asset(cvm_instance):
    """创建或更新资产"""
    # 实例名
    instanceName = cvm_instance.InstanceName
    # 私网地址
    privateIpAddresse = cvm_instance.PrivateIpAddresses[0]
    # 公网IP
    publicIpAddresse = cvm_instance.PublicIpAddresses[0] if len(cvm_instance.PublicIpAddresses) > 0 else ""
    # cvm 标签
    tags = cvm_instance.Tags
    # VPC ID
    vpcId = cvm_instance.VirtualPrivateCloud.VpcId
    # VPC 子网
    subnetId = cvm_instance.VirtualPrivateCloud.SubnetId
    # 业务状态
    restrictState = cvm_instance.RestrictState
    # 操作系统
    osName = cvm_instance.OsName

    # 不是正常状态或者是不需要纳入跳板机管理的实例,删除
    if not QcloudCVMApi.is_normal_cvm(restrictState) or QcloudCVMApi.is_noops_cvm(tags):
        logger.info("delete asset sync qcloud cvm, instance name: %s, ip: %s" % (instanceName, privateIpAddresse))
        delete_asset(privateIpAddresse)
        return

    asset = query_asset_by_ip(privateIpAddresse)
    if not asset:
        # 创建资产
        if query_asset_by_hostname(instanceName):
            hostname = instanceName + "_" + privateIpAddresse
        else:
            hostname = instanceName
        logger.info("create asset sync qcloud cvm, hostname: %s, ip: %s" % (hostname, privateIpAddresse))
        asset = Asset.objects.create(ip=privateIpAddresse,
                                     hostname=hostname,
                                     admin_user=get_os_adminuser(osName),
                                     public_ip=publicIpAddresse)
    else:
        asset = asset[0]
    # 更新 Asset Node 节点
    vpcName = QcloudVpcApi.vpcIdToStr(vpcId)
    subnetName = QcloudVpcApi.subnetIdToStr(subnetId)
    subnet_node = create_or_update_vpc_subnet_node(vpcName, subnetName)
    logger.info("update asset node, asset ip: %s, node vpcname: %s, node subnetname: %s"
                % (privateIpAddresse, vpcName, subnetName))
    asset.nodes.set(subnet_node)


@shared_task
def sync_qcloud_asset():
    """同步腾讯云CVM至Jumpserver资产"""
    offset = 0
    limit = 100
    qcloud_cvm_api = QcloudCVMApi()
    while True:
        cvm_list = qcloud_cvm_api.cvm_list(offset, limit)
        if len(cvm_list) == 0: break
        for cvm in cvm_list:
            create_or_update_asset(cvm)
        offset += limit

@shared_task
@after_app_ready_start
def sync_qcloud_asset_periodic():
    """celery_default.log"""
    tasks = {
        'sync_qcloud_asset_periodic': {
            'task': sync_qcloud_asset.name,
            'interval': None,
            'crontab': '*/30 * * * *',
            'enabled': True,
        }
    }
    create_or_update_celery_periodic_tasks(tasks)