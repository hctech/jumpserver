#!/usr/bin/env python
# coding: utf-8
# Author: huangchao

from jumpserver.const import CONFIG
from common.utils import get_logger

import json
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.cvm.v20170312 import cvm_client, models

logger = get_logger(__file__)


class QcloudVpcApi(object):
    @staticmethod
    def vpcIdToStr(vpcId):
        mapping = {
            "vpc-31ng645r": "xingren-devops",
            "vpc-gik7wn9j": "xingren"
        }
        return mapping.get(vpcId, vpcId)

    @staticmethod
    def subnetIdToStr(subnetId):
        mapping = {
            "subnet-nyu8b3na": "gz4-oa-yunpan",
            "subnet-j66y62qa": "gz4-sensorsdata",
            "subnet-1poz1d2s": "gz3-Ai",
            "subnet-aqa1954g": "default",
            "subnet-9iwh4bfc": "gz3-stg",
            "subnet-mfbuq9le": "gz3-dev-doctorwork",
            "subnet-7ilskj08": "gz4-devops",
            "subnet-qqhaga56": "gz3-devops",
            "subnet-mgt9ymgg": "gz3-prod",
            "subnet-5jd09c6o": "gz3-test",
            "subnet-5vgmbece": "gz2-devops",
            "subnet-ap033n7a": "gz2-test",
            "subnet-nyci1xro": "gz2-dev",
            "subnet-6kkkh98w": "gz2-stg",
            "subnet-ckc0t3y2": "gz2-prod"
        }
        return mapping.get(subnetId, subnetId)


class QcloudCVMApi(object):
    def __init__(self):
        self._secretId = CONFIG.QCLOUD.get("SecretId")
        self._secretKey = CONFIG.QCLOUD.get("SecretKey")
        self._cred = credential.Credential(self._secretId, self._secretKey)
        self.httpProfile = HttpProfile()
        self.httpProfile.endpoint = "cvm.tencentcloudapi.com"
        self.clientProfile = ClientProfile()
        self.clientProfile.httpProfile = self.httpProfile

    def cvm_list(self, offset=0, limit=100, region="ap-guangzhou"):
        """
        获取 cvm 实例列表
        :param offset: 偏移量，从 0 开始
        :param limit: 限制返回值
        :param region: 地域
        :return: cvm instance 列表, tencentcloud.cvm.v20170312.models.Instance
        https://cloud.tencent.com/document/api/213/15753#Instance
        """
        try:
            client = cvm_client.CvmClient(self._cred, region, self.clientProfile)
            req = models.DescribeInstancesRequest()
            # 请求参数
            params = {
                "Offset": offset,
                "Limit": limit
            }
            req.from_json_string(json.dumps(params))
            resp = client.DescribeInstances(req)
            return resp.InstanceSet
        except TencentCloudSDKException as err:
            logger.error("request qcloud cvm list exception: %s" % err)

    @staticmethod
    def is_noops_cvm(tags):
        """
        是否是第三方CVM,不需要接入跳板机管理
        :param tags: models.Instance.Tags cvm 标签列表
        :return boolean
        """
        noops = [tag for tag in tags if tag.Key == "noops" and tag.Value == "1"]
        return True if len(noops) > 0 else False

    @staticmethod
    def is_normal_cvm(restrict_state):
        """
        是否是正常业务状态的实例
        :param restrict_state: models.Instance.RestrictState cvm 实例状态
        :return: boolean
        """
        return True if restrict_state == "NORMAL" else False
