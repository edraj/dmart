import os
from jinja2 import Environment, FileSystemLoader


def generate_email_from_template(template, data):
    environment = Environment(
        loader=FileSystemLoader(os.path.dirname(__file__) + "/templates/")
    )
    match template:
        case "activation":
            template = environment.get_template("activation.html.j2")
            return template.render(
                name=data.get("name"),
                msisdn=data.get("msisdn"),
                shortname=data.get("shortname"),
                link=data.get("link"),
            )

        case "reminder":
            template = environment.get_template("reminder.html.j2")
            return template.render(
                name=data.get("name"),
                link=data.get("link"),
            )
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


print(
    generate_email_from_template(
        "activation",
        {"name": "name", "msisdn": "msisdn", "shortname": "shortname", "link": None},
    )
)
