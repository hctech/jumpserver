#!/usr/bin/env python
# coding: utf-8
# Author: huangchao

from celery import shared_task
from ops.celery.utils import (
    create_or_update_celery_periodic_tasks, disable_celery_periodic_task
)
from ops.celery.decorator import after_app_ready_start
from assets.models.user import SystemUser
from assets.models.asset import Asset, Platform
from assets.models.report import UserPrivilegeReport
from ops.inventory import JMSInventory
from ops.ansible.runner import CommandRunner
from jumpserver.const import CONFIG

from common.utils import get_logger
import os
import xlsxwriter
from django.core.mail import EmailMessage
from django.conf import settings

logger = get_logger(__file__)

BASEDIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORTDIR = os.path.join(BASEDIR, 'report')
if not os.path.isdir(REPORTDIR): os.makedirs(REPORTDIR)

# 报告HTML,用于发送邮件
report_html = '''
<div class="" style="font-family:&quot;font-size:16px;">
	<strong><span style="font-size:18px;">Dear all：</span><span style="font-size:18px;"></span></strong> 
</div>
<p style="font-family:&quot;font-size:16px;">
	&nbsp; &nbsp;<span style="font-size:16px;"> 附件为 {check_month}月份服务器用户&amp;权限报表详情，与上次检查周期相比有变动的使用 “<span style="color:#E53333;">红色</span>“ 标记。</span> 
</p>
<p style="font-family:&quot;font-size:16px;">
	<table style="width:100%;" cellpadding="2" cellspacing="0" border="1" bordercolor="#000000">
		<tbody>
			<tr>
				<td colspan="4" style="text-align:center;background-color:#337FE5;">
					<strong><span style="color:#FFFFFF;">服务器用户权限检查报表</span></strong><br />
				</td>
			</tr>
			<tr>
				<td>
					检测时间
				</td>
				<td>
					{check_time}
				</td>
				<td>
					检测状态
				</td>
				<td>
					{check_status}
				</td>
			</tr>
			<tr>
				<td>
					检测服务器数量
				</td>
				<td>
					{check_host_nums}
				</td>
				<td>
					<span style="font-family:&quot;font-size:14.6667px;">存在用户或权限变更的服务器数量</span><br />
				</td>
				<td>
					{changed_host_nums}
				</td>
			</tr>
		</tbody>
	</table>
</p>
'''

def gen_report(pre_report, current_report):
    """生成报表"""
    report_filename = os.path.join(REPORTDIR, current_report.created.strftime("%Y-%m-%d") + ".xlsx")
    wb = xlsxwriter.Workbook(report_filename)
    # 汇总sheet
    total_worksheet = wb.add_worksheet("汇总")
    total_worksheet.set_column('A:D', 30)
    total_worksheet.merge_range('A1:D1', '服务器用户权限检查汇总报表',
                                     wb.add_format(
                                         {'bold': True, 'align': "center", 'border': True, 'bg_color': '#3498DB',
                                          'font_color': 'white'}))
    # 用户权限详情sheet
    detail_worksheet = wb.add_worksheet("用户权限详情")
    detail_worksheet.write(0, 0, '主机名', wb.add_format(
        {'bold': True, 'align': "center", 'border': True, 'bg_color': '#3498DB',
         'font_color': 'white'}))
    detail_worksheet.write(0, 1, '本次用户&权限', wb.add_format(
        {'bold': True, 'align': "center", 'border': True, 'bg_color': '#3498DB',
         'font_color': 'white'}))
    detail_worksheet.write(0, 2, '上次用户&权限', wb.add_format(
        {'bold': True, 'align': "center", 'border': True, 'bg_color': '#3498DB',
         'font_color': 'white'}))
    detail_worksheet.set_column('A:C', 30)
    detail_workbook_sheet_row = 1


    # 有用户或权限变动的主机数量
    has_changed_count = 0
    # 本次检查主机数&状态
    if current_report.check_status == 0:
        current_host_count = 0
        current_status = '失败'
    else:
        current_host_count = len(current_report.check_result)
        current_status = '成功'
        # 上次运行的结果
        pre_check_result = {} if pre_report is None else pre_report.check_result
        # 遍历本次结果与上次比对
        for hostname, result in current_report.check_result.items():
            pre_host_check_result = pre_check_result.get(hostname, None)
            if pre_host_check_result is not None:
                pre_run_stdout = pre_host_check_result.get('stdout')
            else:
                pre_run_stdout = ''
            current_run_stdout = result.get('stdout', '')
            if current_run_stdout != pre_run_stdout:
                has_changed_count += 1
                detail_worksheet.write(detail_workbook_sheet_row, 0, hostname,
                                            wb.add_format({'font_color': 'red', 'border': True}))
                detail_worksheet.write(detail_workbook_sheet_row, 1, current_run_stdout,
                                            wb.add_format({'font_color': 'red', 'border': True}))
                detail_worksheet.write(detail_workbook_sheet_row, 2, pre_run_stdout,
                                            wb.add_format({'font_color': 'red', 'border': True}))
            else:
                detail_worksheet.write(detail_workbook_sheet_row, 0, hostname,
                                            wb.add_format({'border': True}))
                detail_worksheet.write(detail_workbook_sheet_row, 1, current_run_stdout,
                                            wb.add_format({'border': True}))
                detail_worksheet.write(detail_workbook_sheet_row, 2, pre_run_stdout,
                                            wb.add_format({'border': True}))
            detail_workbook_sheet_row += 1

    total_worksheet.write('A2', '检查时间', wb.add_format({'border': True}))
    total_worksheet.write('B2',  str(current_report.created), wb.add_format({'border': True}))
    total_worksheet.write('C2', '检测状态', wb.add_format({'border': True}))
    total_worksheet.write('D2', current_status, wb.add_format({'border': True}))
    total_worksheet.write('A3', '检查服务器数量', wb.add_format({'border': True}))
    total_worksheet.write('B3', current_host_count, wb.add_format({'border': True}))
    total_worksheet.write('C3', '存在用户或权限变更的服务器数量', wb.add_format({'border': True}))
    total_worksheet.write('D3', has_changed_count, wb.add_format({'border': True, 'font_color': 'red'}))
    wb.close()
    # 生成发送邮件html
    mail_subject = "服务器用户权限%s月份检查报表" % (current_report.created.strftime("%m"))
    mail_from = settings.EMAIL_FROM or settings.EMAIL_HOST_USER
    mail_to = CONFIG.USER_PRIV_REPORT_TO_MAILS
    mail_context = report_html.format(check_month=current_report.created.strftime("%m"),
                                      check_time=str(current_report.created),
                                      check_status=current_status,
                                      check_host_nums=current_host_count,
                                      changed_host_nums=has_changed_count)
    # 发送邮件
    mail_message = EmailMessage(subject=mail_subject, body=mail_context, from_email=mail_from, to=mail_to)
    mail_message.content_subtype = "html"
    mail_message.encoding = "utf-8"
    mail_message.attach_file(report_filename)
    mail_message.send()
    logger.info("用户权限权限检查结果, 检查主机数量: %s, 检查状态: %s, 存在用户或权限变动的主机数: %s"
                % (current_host_count, current_status, has_changed_count))

@shared_task
def user_privilege_report():
    """用户权限检测报表"""
    # 上次检查结果
    last_record = UserPrivilegeReport.objects.filter(check_status=1).order_by('-created')
    if last_record:
        pre_report = last_record.first()
    else:
        pre_report = None
    script_filename = os.path.join(REPORTDIR, "check_user.sh")
    # 检测所有的Linux资产
    linux_platform = Platform.objects.get(name="Linux")
    assets = Asset.objects.filter(platform=linux_platform)
    # 运行ansible的系统用户,该用户需要推送到所有待检查的主机上
    system_user = SystemUser.objects.get(name='huangchao')
    inventory = JMSInventory(assets, run_as='huangchao', system_user=system_user)
    runner = CommandRunner(inventory)
    try:
        res = runner.execute(script_filename, 'all', 'script')
        command_result = res.results_command
        current_report = UserPrivilegeReport.objects.create(check_result=command_result, check_status=1)
    except Exception as e:
        current_report = UserPrivilegeReport.objects.create(run_exception=str(e), check_status=0)
    gen_report(pre_report, current_report)


@shared_task
@after_app_ready_start
def user_privilege_report_periodic():
    """celery_default.log"""
    tasks = {
        'user_privilege_report_periodic': {
            'task': user_privilege_report.name,
            'interval': None,
            'crontab': '0 10 1 * *',
            'enabled': True,
        }
    }
    create_or_update_celery_periodic_tasks(tasks)