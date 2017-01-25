from ..models import Config
from django_netjsonconfig.controller.generics import (
    BaseChecksumView,
    BaseDownloadConfigView,
    BaseReportStatusView
)


class ChecksumView(BaseChecksumView):
    model = Config


class DownloadConfigView(BaseDownloadConfigView):
    model = Config


class ReportStatusView(BaseReportStatusView):
    model = Config


checksum = ChecksumView.as_view()
download_config = DownloadConfigView.as_view()
report_status = ReportStatusView.as_view()
