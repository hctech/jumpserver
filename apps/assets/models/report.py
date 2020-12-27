#!/usr/bin/env python
# coding: utf-8
# Author: huangchao

from django.db import models
from common.fields.model import JsonDictTextField

class UserPrivilegeReport(models.Model):
    check_result = JsonDictTextField(blank=True, null=True)
    check_status = models.IntegerField(default=0)
    exception_msg = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)