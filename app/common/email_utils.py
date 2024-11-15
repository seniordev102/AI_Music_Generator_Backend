import boto3
from pydantic import EmailStr

from app.config import settings


async def send_email(
    recipient: EmailStr, subject: str, name: str, message: str
) -> bool:

    session = boto3.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_DEFAULT_REGION,
    )

    ses = session.client("ses")

    html_template = """
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
        <html
        xmlns="http://www.w3.org/1999/xhtml"
        style="
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            box-sizing: border-box;
            font-size: 14px;
            margin: 0;
        "
        >
        <head>
            <meta name="viewport" content="width=device-width" />
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
            <title>New Message</title>
        </head>
        <body
            itemscope
            itemtype="http://schema.org/EmailMessage"
            style="
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            box-sizing: border-box;
            font-size: 14px;
            -webkit-font-smoothing: antialiased;
            -webkit-text-size-adjust: none;
            width: 100% !important;
            height: 100%;
            line-height: 1.6em;
            background-color: #f6f6f6;
            margin: 0;
            "
            bgcolor="#f6f6f6"
        >
            <table
            class="body-wrap"
            style="
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                box-sizing: border-box;
                font-size: 14px;
                width: 100%;
                background-color: #f6f6f6;
                margin: 0;
            "
            bgcolor="#f6f6f6"
            >
            <tr
                style="
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                box-sizing: border-box;
                font-size: 14px;
                margin: 0;
                "
            >
                <td
                style="
                    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    box-sizing: border-box;
                    font-size: 14px;
                    vertical-align: top;
                    margin: 0;
                "
                valign="top"
                ></td>
                <td
                class="container"
                width="600"
                style="
                    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    box-sizing: border-box;
                    font-size: 14px;
                    vertical-align: top;
                    display: block !important;
                    max-width: 600px !important;
                    clear: both !important;
                    margin: 0 auto;
                "
                valign="top"
                >
                <div
                    class="content"
                    style="
                    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    box-sizing: border-box;
                    font-size: 14px;
                    max-width: 600px;
                    display: block;
                    margin: 0 auto;
                    padding: 20px;
                    "
                >
                    <table
                    class="main"
                    width="100%"
                    cellpadding="0"
                    cellspacing="0"
                    style="
                        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                        box-sizing: border-box;
                        font-size: 14px;
                        border-radius: 3px;
                        background-color: #fff;
                        margin: 0;
                        border: 1px solid #e9e9e9;
                    "
                    bgcolor="#fff"
                    >
                    <tr
                        style="
                        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                        box-sizing: border-box;
                        font-size: 14px;
                        margin: 0;
                        "
                    >
                        <td
                        class="header"
                        style="
                            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                            box-sizing: border-box;
                            font-size: 16px;
                            vertical-align: top;
                            color: #fff;
                            font-weight: 500;
                            text-align: center;
                            border-radius: 3px 3px 0 0;
                            background-color: #ffffff;
                            margin: 0;
                            padding: 20px;
                        "
                        align="center"
                        bgcolor="#FF9F00"
                        valign="top"
                        >
                        <img
                            src="https://iah.fit/wp-content/uploads/2024/04/iah_fit_logo_text_Small-2.png"
                            alt="IAH Fit"
                            style="width: 150px; height: 32px"
                        />
                        </td>
                    </tr>
                    <tr
                        style="
                        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                        box-sizing: border-box;
                        font-size: 14px;
                        margin: 0;
                        "
                    >
                        <td
                        class="content-wrap"
                        style="
                            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                            box-sizing: border-box;
                            font-size: 14px;
                            vertical-align: top;
                            margin: 0;
                            padding: 20px;
                        "
                        valign="top"
                        >
                        <table
                            width="100%"
                            cellpadding="0"
                            cellspacing="0"
                            style="
                            font-family: 'Helvetica Neue', Helvetica, Arial,
                                sans-serif;
                            box-sizing: border-box;
                            font-size: 14px;
                            margin: 0;
                            "
                        >
                            <tr
                            style="
                                font-family: 'Helvetica Neue', Helvetica, Arial,
                                sans-serif;
                                box-sizing: border-box;
                                font-size: 14px;
                                margin: 0;
                            "
                            >
                            <td
                                class="content-block"
                                style="
                                font-family: 'Helvetica Neue', Helvetica, Arial,
                                    sans-serif;
                                box-sizing: border-box;
                                font-size: 14px;
                                vertical-align: top;
                                margin: 0;
                                padding: 0 0 20px;
                                "
                                valign="top"
                            >
                                You have
                                <strong
                                style="
                                    font-family: 'Helvetica Neue', Helvetica, Arial,
                                    sans-serif;
                                    box-sizing: border-box;
                                    font-size: 14px;
                                    margin: 0;
                                "
                                >1 new message</strong
                                >
                                from {recipient}
                            </td>
                            </tr>

                            <tr
                            style="
                                font-family: 'Helvetica Neue', Helvetica, Arial,
                                sans-serif;
                                box-sizing: border-box;
                                font-size: 14px;
                                margin: 0;
                            "
                            >
                            <td
                                class="content-block"
                                style="
                                font-family: 'Helvetica Neue', Helvetica, Arial,
                                    sans-serif;
                                box-sizing: border-box;
                                font-size: 14px;
                                vertical-align: top;
                                margin: 0;
                                padding: 0 0 10px;
                                "
                                valign="top"
                            >
                                Name : {name}
                            </td>
                            </tr>

                            <tr
                            style="
                                font-family: 'Helvetica Neue', Helvetica, Arial,
                                sans-serif;
                                box-sizing: border-box;
                                font-size: 14px;
                                margin: 0;
                            "
                            >
                            <td
                                class="content-block"
                                style="
                                font-family: 'Helvetica Neue', Helvetica, Arial,
                                    sans-serif;
                                box-sizing: border-box;
                                font-size: 14px;
                                vertical-align: top;
                                margin: 0;
                                padding: 0 0 20px;
                                "
                                valign="top"
                            >
                                Email : {recipient}
                            </td>
                            </tr>
                            <tr
                            style="
                                font-family: 'Helvetica Neue', Helvetica, Arial,
                                sans-serif;
                                box-sizing: border-box;
                                font-size: 14px;
                                margin: 0;
                            "
                            >
                            <td
                                class="content-block"
                                style="
                                font-family: 'Helvetica Neue', Helvetica, Arial,
                                    sans-serif;
                                box-sizing: border-box;
                                font-size: 14px;
                                vertical-align: top;
                                margin: 0;
                                padding: 0 0 20px;
                                "
                                valign="top"
                            >
                                {message}
                            </td>
                            </tr>
                            <tr
                            style="
                                font-family: 'Helvetica Neue', Helvetica, Arial,
                                sans-serif;
                                box-sizing: border-box;
                                font-size: 14px;
                                margin: 0;
                            "
                            ></tr>
                            <tr
                            style="
                                font-family: 'Helvetica Neue', Helvetica, Arial,
                                sans-serif;
                                box-sizing: border-box;
                                font-size: 14px;
                                margin: 0;
                            "
                            >
                            <td
                                class="content-block"
                                style="
                                font-family: 'Helvetica Neue', Helvetica, Arial,
                                    sans-serif;
                                box-sizing: border-box;
                                font-size: 14px;
                                vertical-align: top;
                                margin: 0;
                                padding: 0 0 20px;
                                "
                                valign="top"
                            >
                                Thanks for choosing iah.fit Inc.
                            </td>
                            </tr>
                        </table>
                        </td>
                    </tr>
                    </table>
                    <div
                    class="footer"
                    style="
                        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                        box-sizing: border-box;
                        font-size: 14px;
                        width: 100%;
                        clear: both;
                        color: #999;
                        margin: 0;
                        padding: 20px;
                    "
                    >
                    <table
                        width="100%"
                        style="
                        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                        box-sizing: border-box;
                        font-size: 14px;
                        margin: 0;
                        "
                    >
                        <tr
                        style="
                            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                            box-sizing: border-box;
                            font-size: 14px;
                            margin: 0;
                        "
                        >
                        <td
                            class="aligncenter content-block"
                            style="
                            font-family: 'Helvetica Neue', Helvetica, Arial,
                                sans-serif;
                            box-sizing: border-box;
                            font-size: 12px;
                            vertical-align: top;
                            color: #999;
                            text-align: center;
                            margin: 0;
                            padding: 0 0 20px;
                            "
                            align="center"
                            valign="top"
                        >
                            <a
                            href="https://iah.fit"
                            style="
                                font-family: 'Helvetica Neue', Helvetica, Arial,
                                sans-serif;
                                box-sizing: border-box;
                                font-size: 12px;
                                color: #999;
                                text-decoration: underline;
                                margin: 0;
                            "
                            >iah.fit</a
                            >
                        </td>
                        </tr>
                    </table>
                    </div>
                </div>
                </td>
                <td
                style="
                    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    box-sizing: border-box;
                    font-size: 14px;
                    vertical-align: top;
                    margin: 0;
                "
                valign="top"
                ></td>
            </tr>
            </table>
        </body>
        </html>
    """

    html_message = html_template.format(recipient=recipient, message=message, name=name)

    response = ses.send_email(
        Source=settings.SMTP_EMAIL,
        Destination={"ToAddresses": [recipient]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Html": {"Data": html_message}},  # Here you specify HTML content
        },
    )

    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        return True
    else:
        return False
