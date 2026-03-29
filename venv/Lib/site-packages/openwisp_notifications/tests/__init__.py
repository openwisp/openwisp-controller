_test_batch_email_notification_email_body = """
[example.com] 4 unread notifications since {datetime_str}


- Default notification with default verb and level info by Tester Tester (test org)
  Description: Test Notification
  Date & Time: {datetime_str}
  URL: https://example.com/api/v1/notifications/notification/{notification_id}/redirect/

- Test Notification
  Description: Test Notification
  Date & Time: {datetime_str}

- Test Notification
  Description: Test Notification
  Date & Time: {datetime_str}
  URL: https://localhost:8000/admin

- Test Notification
  Description: Test Notification
  Date & Time: {datetime_str}
  URL: https://localhost:8000/admin
"""

_test_batch_email_notification_email_html = """
<div class="container">
  <div class="logo-container">
    <img
      src="https://raw.githubusercontent.com/openwisp/openwisp-utils/master/openwisp_utils/static/openwisp-utils/images/openwisp-logo.png"
      alt="Logo" class="logo">
  </div>
  <div class="email-info">This email is sent to <u>admin@admin.com</u> from <a
    href="https://example.com/admin/">[example.com]</a></div>
  <div class="box">
    <div class="icon-container">
      <img src="https://example.com/static/ui/openwisp/images/email.png" alt="email icon">
    </div>
    <div class="sysname-container">example.com</div>
    <div class="email-title">4 unread notifications</div>
    <div class="subtitle">Since {datetime_str}</div>
    <hr>
    <div class="email-content">
      <div>
        <a class="alert-link"
          href="https://example.com/api/v1/notifications/notification/{notification_id}/redirect/"
          target="_blank">
          <table class="alert">
            <tbody>
              <tr>
                <td>
                  <div>
                    <span class="badge info">info</span>
                    <div class="title">
                      <p>Default notification with default verb and level info by Tester Tester (test org)</p>
                    </div>
                  </div>
                </td>
                <td class="right-arrow-container"> <img class="right-arrow"
                  src="https://example.com/static/ui/openwisp/images/right-arrow.png" alt="right-arrow"> </td>
              </tr>
              <tr>
                <td>
                  <hr>
                  <div>
                    <p class="timestamp">{datetime_str}</p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </a>
        <table class="alert">
          <tbody>
            <tr>
              <td>
                <div>
                  <span class="badge info">info</span>
                  <div class="title">
                    <p>Test Notification</p>
                  </div>
                </div>
              </td>
              <td class="right-arrow-container"> <img class="right-arrow"
                src="https://example.com/static/ui/openwisp/images/right-arrow.png" alt="right-arrow"> </td>
            </tr>
            <tr>
              <td>
                <hr>
                <div>
                  <p class="timestamp">{datetime_str}</p>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <a class="alert-link" href="https://localhost:8000/admin" target="_blank">
          <table class="alert">
            <tbody>
              <tr>
                <td>
                  <div>
                    <span class="badge info">info</span>
                    <div class="title">
                      <p>Test Notification</p>
                    </div>
                  </div>
                </td>
                <td class="right-arrow-container"> <img class="right-arrow"
                  src="https://example.com/static/ui/openwisp/images/right-arrow.png" alt="right-arrow"> </td>
              </tr>
              <tr>
                <td>
                  <hr>
                  <div>
                    <p class="timestamp">{datetime_str}</p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </a>
        <a class="alert-link" href="https://localhost:8000/admin" target="_blank">
          <table class="alert">
            <tbody>
              <tr>
                <td>
                  <div>
                    <span class="badge info">info</span>
                    <div class="title">
                      <p>Test Notification</p>
                    </div>
                  </div>
                </td>
                <td class="right-arrow-container"> <img class="right-arrow"
                  src="https://example.com/static/ui/openwisp/images/right-arrow.png" alt="right-arrow"> </td>
              </tr>
              <tr>
                <td>
                  <hr>
                  <div>
                    <p class="timestamp">{datetime_str}</p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </a>
      </div>
    </div>
  </div>
  <div class="footer">
    <p>To stop receiving all email notifications, <a href="{unsubscribe_url}">unsubscribe</a>.
    </p>
  </div>
</div>
"""
