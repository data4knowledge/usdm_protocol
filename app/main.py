import os
import json
from fastapi import FastAPI, Request, status, Form
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.database.database import Database
from d4k_ms_ui.release_notes import ReleaseNotes
from d4k_ms_base.service_environment import ServiceEnvironment
from d4k_ms_base import application_logger
from app.github.github import get_access_token, get_user_data
from app.file_handling.data_files import DataFiles
from app.__info__ import VERSION, SYSTEM_NAME
from app.configuration.configuration import application_configuration
from app.file_handling.usdm_file import USDMFile
from app.file_handling.template_file import TemplateFile


app = FastAPI(
    title=SYSTEM_NAME,
    description="A simple tool to edit USDM protocol content",
    version=VERSION,
)

dir_path = os.path.dirname(os.path.realpath(__file__))
static_path = os.path.join(dir_path, "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")
application_logger.info(f"Static dir set to '{static_path}'")

templates_path = os.path.join(dir_path, "templates")
templates = Jinja2Templates(directory=templates_path)
application_logger.info(f"Template dir set to '{templates_path}'")

DataFiles.check()
DataFiles.clean_and_tidy()

se = ServiceEnvironment()
cookie_name = se.get("COOKIE_NAME")
cookie_value = se.get("COOKIE_VALUE")
backdoor = se.get("BACKDOOR")


class AuthenticationException(Exception):
    def __init__(self, name: str):
        self.name = name


@app.exception_handler(AuthenticationException)
async def authentication_exception_handler(
    request: Request, exc: AuthenticationException
):
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)


def check_simple_authentication(request):
    value = request.cookies.get(cookie_name)
    if value == cookie_value:
        return True
    raise AuthenticationException(name="User needs to authenticate")


@app.get("/")
def home_page(request: Request):
    client_id = se.get("CLIENT_ID")
    return templates.TemplateResponse(
        "home/index.html", {"request": request, "client_id": client_id}
    )


@app.get("/github/callback")
async def login(request: Request):
    request_token = request.query_params["code"]
    CLIENT_ID = se.get("CLIENT_ID")
    CLIENT_SECRET = se.get("CLIENT_SECRET")
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET, request_token)
    user_data = get_user_data(access_token)
    application_logger.info(f"Login by: {user_data['name']}")
    response = RedirectResponse(url="/home", status_code=status.HTTP_302_FOUND)
    response.set_cookie(cookie_name, value=cookie_value, httponly=True, expires=7200)
    return response


@app.get(f"/{backdoor}")
async def login(request: Request):
    application_logger.info(f"Login by: Backdoor")
    response = RedirectResponse(url="/home", status_code=status.HTTP_302_FOUND)
    response.set_cookie(cookie_name, value=cookie_value, httponly=True, expires=3600)
    return response


@app.get("/status")
def status_page(request: Request):
    check_simple_authentication(request)
    return templates.TemplateResponse(
        "status/status.html",
        {
            "request": request,
            "release_notes": ReleaseNotes().notes(),
            "data": {"system": SYSTEM_NAME, "version": VERSION},
        },
    )


@app.get("/logout/")
async def logout(request: Request):
    check_simple_authentication(request)
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key=cookie_name)
    return response


@app.get("/home")
async def home(request: Request):
    check_simple_authentication(request)
    data = []
    dirs = DataFiles.dirs()
    for dir in dirs:
        print(f"DIR: {dir}")
        usdm = USDMFile(dir["file"])
        result = {"id": dir["file"], "study": usdm.study.summary(), "templates": usdm.study.document_templates()}
        print(f"RESULT: {result}")
        data.append(result)
    response = templates.TemplateResponse(
        "home/home.html", {"request": request, "data": data}
    )
    return response


@app.get("/import/usdm")
def import_usdm(request: Request):
    check_simple_authentication(request)
    return templates.TemplateResponse(request, "import/import_json.html", {})


@app.post("/import/usdm")
async def import_usdm_process(request: Request):
    check_simple_authentication(request)
    print("XXXX1")
    form = await request.form()
    files = form.getlist("files")
    data_files = DataFiles()
    print(f"FILES: {data_files}")
    for v in files:
        filename = v.filename
        contents = await v.read()
        file_root, file_extension = os.path.splitext(filename)
        print(f"EXT: {file_root}, {file_extension}")
        if file_extension == ".json":
            data_files.new()
            data_files._save_json_file(contents, filename)
    return templates.TemplateResponse(request, "import/partials/upload_success.html", {})


@app.get("/edit/{uuid}")
async def home(request: Request, uuid: str, template: str):
    check_simple_authentication(request)
    template = TemplateFile(uuid, template)
    data = template.from_usdm()
    response = templates.TemplateResponse(
        "home/edit.html", {"request": request, "data": template.toc_sections()}
    )
    return response

@app.get("/sections/{section}")
async def get_section(request: Request, section: str):
    check_simple_authentication(request)
    # database = Database()
    data = database.get_section(section)
    can_add = {
        "child": database.can_add_child_section(section),
        "sibling": database.can_add_sibling_section(section),
    }
    response = templates.TemplateResponse(
        "home/partials/section.html",
        {
            "request": request,
            "key": section,
            "data": data,
            "can_add": can_add,
            "toc": None,
            "cursor": 0,
        },
    )
    return response


@app.post("/sections/{section}")
async def post_section(request: Request, section: str, text: str = Form(...)):
    check_simple_authentication(request)
    data = database.put_section(section, text)
    return {}


@app.get("/sections/{section}/document")
async def document(request: Request, section: str):
    check_simple_authentication(request)
    data = database.get_section(section)
    response = templates.TemplateResponse(
        "home/partials/document.html",
        {"request": request, "key": section, "data": data},
    )
    return response


@app.post("/sections/{section}/addSibling")
async def post_section(request: Request, section: str):
    check_simple_authentication(request)
    new_section = database.add_sibling_section(section)
    if new_section:
        data = database.get_section(new_section)
        can_add = {
            "child": database.can_add_child_section(section),
            "sibling": database.can_add_sibling_section(section),
        }
        toc = database.toc_sections()
        return templates.TemplateResponse(
            "home/partials/section.html",
            {
                "request": request,
                "key": new_section,
                "data": data,
                "can_add": can_add,
                "toc": toc,
                "cursor": 0,
            },
        )
    else:
        return templates.TemplateResponse(
            "errors/partials/errors.html",
            {"request": request, "data": {"error": f"Failed to add section {section}"}},
        )


@app.post("/sections/{section}/addChild")
async def post_section(request: Request, section: str):
    check_simple_authentication(request)
    new_section = database.add_child_section(section)
    if new_section:
        data = database.get_section(new_section)
        can_add = {
            "child": database.can_add_child_section(section),
            "sibling": database.can_add_sibling_section(section),
        }
        toc = database.toc_sections()
        return templates.TemplateResponse(
            "home/partials/section.html",
            {
                "request": request,
                "key": new_section,
                "data": data,
                "can_add": can_add,
                "toc": toc,
                "cursor": 0,
            },
        )
    else:
        return templates.TemplateResponse(
            "errors/partials/errors.html",
            {"request": request, "data": {"error": f"Failed to add section {section}"}},
        )


@app.delete("/sections/{section}")
async def post_section(request: Request, section: str):
    check_simple_authentication(request)
    # database = Database()
    deleted = database.delete_section(section)
    if deleted:
        data = database.get_section("1")
        can_add = {
            "child": database.can_add_child_section("1"),
            "sibling": database.can_add_sibling_section("1"),
        }
        toc = database.toc_sections()
        return templates.TemplateResponse(
            "home/partials/section.html",
            {
                "request": request,
                "key": "1",
                "data": data,
                "can_add": can_add,
                "toc": toc,
                "cursor": 0,
            },
        )
    else:
        return templates.TemplateResponse(
            "errors/partials/errors.html",
            {
                "request": request,
                "data": {"error": f"Failed to delete section {section}"},
            },
        )


@app.post("/sections/{section}/usdm")
async def post_section(
    request: Request,
    section: str,
    type: str,
    textCursor: int = Form(...),
    textEnd: int = Form(default=None),
):
    check_simple_authentication(request)
    print(f"USDM: Section={section} @ {textCursor} ... {textEnd}, {type}")
    data = database.insert_usdm(section, type, textCursor)
    can_add = {
        "child": database.can_add_child_section(section),
        "sibling": database.can_add_sibling_section(section),
    }
    response = templates.TemplateResponse(
        "home/partials/section.html",
        {
            "request": request,
            "key": section,
            "data": data,
            "can_add": can_add,
            "toc": None,
            "cursor": textCursor,
        },
    )
    return response


@app.get("/sections/{section}/title")
async def get_title(request: Request, section: str):
    check_simple_authentication(request)
    data = database.get_section(section)
    response = templates.TemplateResponse(
        "home/partials/section_title.html",
        {"request": request, "key": section, "data": data},
    )
    return response


@app.post("/sections/{section}/title")
async def put_title(
    request: Request, section: str, section_title_input: str = Form(...)
):
    check_simple_authentication(request)
    data = database.put_section_title(section, section_title_input)
    data = database.get_section(section)
    can_add = {
        "child": database.can_add_child_section(section),
        "sibling": database.can_add_sibling_section(section),
    }
    toc = database.toc_sections()
    response = templates.TemplateResponse(
        "home/partials/section.html",
        {
            "request": request,
            "key": section,
            "data": data,
            "can_add": can_add,
            "toc": toc,
            "cursor": 0,
        },
    )
    return response


@app.get("/download")
async def get_csv(request: Request):
    check_simple_authentication(request)
    full_path, filename, media_type = database.download_excel()
    return FileResponse(path=full_path, filename=filename, media_type=media_type)
