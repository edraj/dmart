from jinja2 import Environment, FileSystemLoader
from pathlib import Path


def generate_email_from_template(template, data):
    templates_dir = Path(__file__).resolve().parent / "templates"
    environment = Environment(
        loader=FileSystemLoader(str(templates_dir))
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
