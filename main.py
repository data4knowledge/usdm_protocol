from fastapi import FastAPI, Depends, HTTPException, Request, status, Form, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from d4kms_ui.release_notes import ReleaseNotes
from utility.database import Database
from d4kms_generic.service_environment import ServiceEnvironment
from d4kms_generic import application_logger
# from utility.uml_view import UMLView
from d4kms_ui import get_access_token, get_user_data
# from utility.uml_views import m11_uml, full_uml

import logging

VERSION = '0.1'
SYSTEM_NAME = "Protocol to USDM"

app = FastAPI(
  title = SYSTEM_NAME,
  description = "A simple tool to convert PDF protcols to USDM",
  version = VERSION
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

se = ServiceEnvironment()
database = Database()
cookie_name = se.get("COOKIE_NAME")
cookie_value = se.get("COOKIE_VALUE")
backdoor = se.get("BACKDOOR")

class AuthenticationException(Exception):
  def __init__(self, name: str):
    self.name = name

@app.exception_handler(AuthenticationException)
async def authentication_exception_handler(request: Request, exc: AuthenticationException):
  return RedirectResponse(url='/', status_code=status.HTTP_302_FOUND)

def check_simple_authentication(request):
  value = request.cookies.get(cookie_name)
  if value == cookie_value:
    return True
  raise AuthenticationException(name="User needs to authenticate")

@app.get("/")
def home_page(request: Request):
  client_id = se.get("CLIENT_ID")
  return templates.TemplateResponse('home/index.html', {"request": request, "client_id": client_id})

@app.get("/github/callback")
async def login(request: Request):
  request_token = request.query_params['code']
  CLIENT_ID = se.get('CLIENT_ID')
  CLIENT_SECRET = se.get('CLIENT_SECRET')
  access_token = get_access_token(CLIENT_ID, CLIENT_SECRET, request_token)
  user_data = get_user_data(access_token)
  application_logger.info(f"Login by: {user_data['name']}")
  response = RedirectResponse(url='/home', status_code=status.HTTP_302_FOUND)
  response.set_cookie(cookie_name, value=cookie_value, httponly=True, expires=7200)
  return response

@app.get(f"/backdoor/{backdoor}")
async def login(request: Request):
  application_logger.info(f"Login by: Backdoor")
  response = RedirectResponse(url='/home', status_code=status.HTTP_302_FOUND)
  response.set_cookie(cookie_name, value=cookie_value, httponly=True, expires=3600)
  return response

@app.get("/status")
def status_page(request: Request):
  check_simple_authentication(request)
  return templates.TemplateResponse(
    'status/status.html', 
    { 
      "request": request, 
      "release_notes": ReleaseNotes().notes(), 
      "data": { 'system': SYSTEM_NAME, 'version': VERSION }
    }
  )

@app.get("/logout/")
async def logout(request: Request):
  check_simple_authentication(request)
  response = RedirectResponse(url='/', status_code=status.HTTP_302_FOUND)
  response.delete_cookie(key=cookie_name)
  return response

@app.get('/home')
async def home(request: Request):
  check_simple_authentication(request)
  data = database.toc_sections()
  print(f"ToC: {data}")
  response = templates.TemplateResponse('home/home.html', { "request": request, 'data': data})
  return response

@app.get('/sections/{section}')
async def get_section(request: Request, section: str):
  check_simple_authentication(request)
  data = database.get_section(section)
  print(f"DATA: {data}")
  response = templates.TemplateResponse('home/partials/section.html', { "request": request, 'key': section, 'data': data})
  return response

@app.post('/sections/{section}')
async def post_section(request: Request, section: str, text: str = Form(...)):
  check_simple_authentication(request)
  data = database.put_section(section, text)
  response = templates.TemplateResponse('home/partials/section.html', { "request": request, 'key': section, 'data': data})
  return response

@app.get('/sections/{section}/document')
async def document(request: Request, section: str):
  check_simple_authentication(request)
  data = database.get_section(section)
  print(f"DATA: {data}")
  response = templates.TemplateResponse('home/partials/document.html', { "request": request, 'key': section, 'data': data})
  return response

