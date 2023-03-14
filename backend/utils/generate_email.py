start_tag = """<!DOCTYPE html>
<html lang="en">
  <head>
    <title>Email</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  </head>
  <body style="margin: 0; padding: 0">
"""
end_tag = """</body>
</html>
"""


def generate_email_from_template(template, data):
    match template:
        case "activation":
            return f"""{start_tag}
<p>Hi {data.get("name")}</p>
<p>MSISDN: {data.get("msisdn")}</p>
<p>Username: {data.get("shortname")}</p>

<p>Welcome, we're happy to see you on board!</p>

<p>Only Few steps are left to activate your account, please use the below account activation link.</p>

<p>Activation Link:</p>

<a href="{data["link"]}">{data["link"]}</a>

<p>Regards,</p>


{end_tag}"""
        case "reminder":
            return f"""{start_tag}
<p>Hi {data["name"]},</p>

<p>We would like to remind you to activate your account. We will be happy to see you on board!</p>

<p>Few steps are left to activate your account, please use the below account activation link.</p>

<p>Activation Link:</p>

{data["link"]}

<p>Regards,</p>


{end_tag}"""
        case _:
            return ""


def generate_subject(template):
    match template:
        case "activation":
            return "Welcome to our Platform!"
        case "reminder":
            return "[Reminder] Activate Your Account"
        case _:
            return ""
