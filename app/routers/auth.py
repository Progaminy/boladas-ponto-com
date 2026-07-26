import uuid

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from app import auth, db
from app.categories import list_categories
from app.models import BusinessInput, UserCreate
from app.templating import templates

router = APIRouter()


@router.get("/termos", response_class=HTMLResponse)
def terms_page(request: Request):
    return templates.TemplateResponse(request, "terms.html", {})


@router.get("/registar/empresa", response_class=HTMLResponse)
def register_business_form(request: Request):
    return templates.TemplateResponse(
        request, "register_business.html",
        {"error": None, "categories": list_categories()},
    )


@router.post("/registar/empresa", response_class=HTMLResponse)
def register_business_submit(
    request: Request,
    business_name: str = Form(...),
    category: str = Form(...),
    category_custom: str | None = Form(None),
    location: str | None = Form(None),
    business_contact: str = Form(...),
    phone_prefix: str | None = Form(None),
    description: str | None = Form(None),
    responsible_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    terms_accepted: str | None = Form(None),
):
    """Cadastro direto de empresa: cria a conta de acesso e a empresa num só
    passo, para quem só quer registar o negócio e não uma conta pessoal."""

    def erro(mensagem: str, codigo: int = 422):
        return templates.TemplateResponse(
            request, "register_business.html",
            {"error": mensagem, "categories": list_categories()},
            status_code=codigo,
        )

    if terms_accepted != "on":
        return erro("Tens de ler e concordar com os Termos de Uso para criar conta.")

    from app.currencies import format_contact
    final_business_contact = format_contact(phone_prefix, business_contact)

    try:
        conta = UserCreate(email=email, password=password, display_name=responsible_name)
        negocio = BusinessInput(
            name=business_name,
            category=(category_custom or "").strip() or category,
            description=description or None,
            location=location or None,
            contact=final_business_contact,
            phone_prefix=phone_prefix,
        )
    except ValidationError as exc:
        return erro(exc.errors()[0]["msg"])

    if db.get_user_by_email(conta.email) is not None:
        return erro(
            "Já existe uma conta com este email. Entra e usa «Nova empresa» "
            "para registar outro negócio na mesma conta.",
            codigo=409,
        )

    user_id = uuid.uuid4().hex
    db.create_user(user_id, conta.email, auth.hash_password(conta.password), conta.display_name)

    business_id = uuid.uuid4().hex
    db.create_business(business_id, user_id, negocio)

    auth.login_user(request, user_id)
    return RedirectResponse(f"/negocio/{business_id}", status_code=303)


@router.get("/registar", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse(request, "register.html", {"error": None})


@router.post("/registar", response_class=HTMLResponse)
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(...),
    terms_accepted: str | None = Form(None),
):
    if terms_accepted != "on":
        return templates.TemplateResponse(
            request, "register.html",
            {"error": "Tens de ler e concordar com os Termos de Uso para criar conta."},
            status_code=422,
        )

    try:
        data = UserCreate(email=email, password=password, display_name=display_name)
    except ValidationError as exc:
        return templates.TemplateResponse(
            request, "register.html", {"error": exc.errors()[0]["msg"]}, status_code=422
        )

    if db.get_user_by_email(data.email) is not None:
        return templates.TemplateResponse(
            request, "register.html", {"error": "Já existe uma conta com este email."},
            status_code=409,
        )

    user_id = uuid.uuid4().hex
    db.create_user(user_id, data.email, auth.hash_password(data.password), data.display_name)
    auth.login_user(request, user_id)
    return RedirectResponse("/explorar", status_code=303)


@router.get("/entrar", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/entrar", response_class=HTMLResponse)
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    email = email.strip().lower()
    user = db.get_user_by_email(email)
    if user is None or not auth.verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            request, "login.html", {"error": "Email ou password incorretos."}, status_code=401
        )

    auth.login_user(request, user["user_id"])
    return RedirectResponse("/explorar", status_code=303)


@router.post("/sair")
def logout(request: Request):
    auth.logout_user(request)
    return RedirectResponse("/", status_code=303)
