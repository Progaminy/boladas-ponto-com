import uuid

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from app import auth, db
from app.categories import list_categories
from app.currencies import format_contact, list_phone_prefixes
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
    return templates.TemplateResponse(
        request, "register.html",
        {"error": None, "phone_prefixes": list_phone_prefixes()},
    )


@router.post("/registar", response_class=HTMLResponse)
def register_submit(
    request: Request,
    auth_method: str = Form("email"),
    email: str | None = Form(None),
    phone_prefix: str | None = Form(None),
    phone: str | None = Form(None),
    password: str = Form(...),
    display_name: str = Form(...),
    terms_accepted: str | None = Form(None),
):
    if terms_accepted != "on":
        return templates.TemplateResponse(
            request, "register.html",
            {
                "error": "Tens de ler e concordar com os Termos de Uso para criar conta.",
                "phone_prefixes": list_phone_prefixes(),
            },
            status_code=422,
        )

    from app.currencies import format_contact

    if auth_method == "phone" or (phone and phone.strip() and not (email or "").strip()):
        if not (phone or "").strip():
            return templates.TemplateResponse(
                request, "register.html",
                {"error": "Indica um número de telefone válido.", "phone_prefixes": list_phone_prefixes()},
                status_code=422,
            )
        full_phone = format_contact(phone_prefix, phone.strip())
        if db.get_user_by_phone(full_phone) is not None:
            return templates.TemplateResponse(
                request, "register.html",
                {"error": "Já existe uma conta associada a este número de telefone.", "phone_prefixes": list_phone_prefixes()},
                status_code=409,
            )
        user_id = uuid.uuid4().hex
        db.create_user_full(
            user_id=user_id,
            display_name=display_name.strip(),
            phone=full_phone,
            phone_prefix=phone_prefix,
            password_hash=auth.hash_password(password),
            auth_provider="phone",
        )
        auth.login_user(request, user_id)
        return RedirectResponse("/explorar", status_code=303)

    # Registo por Email
    clean_email = (email or "").strip().lower()
    if not clean_email or "@" not in clean_email or "." not in clean_email:
        return templates.TemplateResponse(
            request, "register.html",
            {"error": "Indica um email válido.", "phone_prefixes": list_phone_prefixes()},
            status_code=422,
        )

    if db.get_user_by_email(clean_email) is not None:
        return templates.TemplateResponse(
            request, "register.html",
            {"error": "Já existe uma conta com este email.", "phone_prefixes": list_phone_prefixes()},
            status_code=409,
        )

    user_id = uuid.uuid4().hex
    db.create_user_full(
        user_id=user_id,
        display_name=display_name.strip(),
        email=clean_email,
        password_hash=auth.hash_password(password),
        auth_provider="email",
    )
    auth.login_user(request, user_id)
    return RedirectResponse("/explorar", status_code=303)


@router.get("/entrar", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(
        request, "login.html",
        {"error": None, "phone_prefixes": list_phone_prefixes()},
    )


@router.post("/entrar", response_class=HTMLResponse)
def login_submit(
    request: Request,
    email: str | None = Form(None),
    identifier: str | None = Form(None),
    password: str = Form(...),
):
    target = (identifier or email or "").strip()
    if not target:
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "Indica o teu email ou número de telefone.", "phone_prefixes": list_phone_prefixes()},
            status_code=401,
        )

    user = db.get_user_by_email_or_phone(target)
    if user is None or not auth.verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "Email/Telefone ou password incorretos.", "phone_prefixes": list_phone_prefixes()},
            status_code=401,
        )

    auth.login_user(request, user["user_id"])
    return RedirectResponse("/explorar", status_code=303)


@router.get("/auth/google", response_class=HTMLResponse)
@router.post("/auth/google", response_class=HTMLResponse)
def google_auth(
    request: Request,
    google_id: str | None = Form(None),
    email: str | None = Form(None),
    name: str | None = Form(None),
):
    """Registo e Entrada rápida com Conta Google."""
    target_google_id = (google_id or request.query_params.get("google_id") or "google_demo_user").strip()
    target_email = (email or request.query_params.get("email") or "utilizador.google@gmail.com").strip().lower()
    target_name = (name or request.query_params.get("name") or "Utilizador Google").strip()

    user = db.get_user_by_google_id(target_google_id) or db.get_user_by_email(target_email)
    if user is None:
        user_id = uuid.uuid4().hex
        db.create_user_full(
            user_id=user_id,
            display_name=target_name,
            email=target_email,
            google_id=target_google_id,
            auth_provider="google",
        )
        auth.login_user(request, user_id)
    else:
        auth.login_user(request, user["user_id"])

    return RedirectResponse("/explorar", status_code=303)


@router.post("/sair")
def logout(request: Request):
    auth.logout_user(request)
    return RedirectResponse("/", status_code=303)
