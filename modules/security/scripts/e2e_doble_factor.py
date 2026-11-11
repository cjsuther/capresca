#!/usr/bin/env python3
"""E2E del doble factor contra un TokenServer REAL (local), a través del gateway.

Calcula los códigos TOTP como lo hace Google/Microsoft Authenticator, a partir del secreto que devuelve
el enrolamiento. Sólo usa la biblioteca estándar.

    CAPRESCA_URL=http://127.0.0.1:18000          # el gateway (proxy) con TOKENSERVER_ENABLED=true
    E2E_ADMIN_USER=admin E2E_ADMIN_PASSWORD=...  # admin de security (seed)
    TOKENSERVER_URL=http://localhost:8000/v1 TOKENSERVER_API_KEY=tsk_...   # SÓLO un tenant de PRUEBA
    [SECURITY_SIN_TOKENSERVER_URL=http://127.0.0.1:18002]  # security con TokenServer inalcanzable (opcional)
    python3 modules/security/scripts/e2e_doble_factor.py

NUNCA correrlo contra producción: crea usuarios, los bloquea y resetea su 2FA.
"""
import base64, hashlib, hmac, json, os, struct, sys, time, urllib.error, urllib.parse, urllib.request

GW = os.environ.get("CAPRESCA_URL", "http://127.0.0.1:18000").rstrip("/")
TS = os.environ["TOKENSERVER_URL"].rstrip("/")
TS_KEY = os.environ["TOKENSERVER_API_KEY"]
ADMIN_USER = os.environ.get("E2E_ADMIN_USER", "admin")
ADMIN_PASS = os.environ["E2E_ADMIN_PASSWORD"]
SIN_TS = os.environ.get("SECURITY_SIN_TOKENSERVER_URL", "")

for url in (GW, TS):
    host = urllib.parse.urlparse(url).hostname
    if host not in ("localhost", "127.0.0.1", "::1"):
        sys.exit(f"Este e2e sólo corre contra servicios locales (no {host}).")


def req(method, url, body=None, token=None, headers=None):
    h = {"Content-Type": "application/json", **(headers or {})}
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None), {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            data = json.loads(raw) if raw else None
        except ValueError:
            data = {"raw": raw[:200].decode(errors="replace")}
        return e.code, data, {k.lower(): v for k, v in e.headers.items()}


def gw(method, path, body=None, token=None, headers=None):
    return req(method, GW + path, body, token, headers)


def totp(secret_b32, offset=0):
    key = base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8))
    digest = hmac.new(key, struct.pack(">Q", int(time.time() // 30) + offset), hashlib.sha1).digest()
    o = digest[-1] & 0x0F
    return "%06d" % ((struct.unpack(">I", digest[o:o + 4])[0] & 0x7FFFFFFF) % 1_000_000)


_ultimo_paso = {}


def codigo_nuevo(secret):
    """Anti-replay: cada código sirve una vez. Espera al próximo paso de 30 s si este ya se usó."""
    paso = int(time.time() // 30)
    if _ultimo_paso.get(secret) == paso:
        time.sleep(30 - time.time() % 30 + 0.5)
    elif time.time() % 30 > 27:
        time.sleep(30 - time.time() % 30 + 0.5)
    _ultimo_paso[secret] = int(time.time() // 30)
    return totp(secret)


ok = 0


def check(cond, msg, extra=None):
    global ok
    if not cond:
        print(f"  ✗ {msg}  {extra if extra is not None else ''}")
        sys.exit(1)
    ok += 1
    print(f"  ✓ {msg}")


def login(user, pwd):
    return gw("POST", "/api/auth/login", {"username": user, "password": pwd})


def enrolar_y_activar(token):
    s, en, _ = gw("POST", "/api/auth/2fa/enrolar", token=token)
    check(s == 200 and en["qr_png_base64"] and en["secret"], "enrolar devuelve QR y secreto", (s, en))
    check(base64.b64decode(en["qr_png_base64"])[:4] == b"\x89PNG", "el QR es un PNG")
    s, act, _ = gw("POST", "/api/auth/2fa/activar", {"token_id": en["token_id"], "code": codigo_nuevo(en["secret"])}, token)
    check(s == 200 and act["access_token"], "activar con el primer código", (s, act))
    return en, act


suf = str(int(time.time()))[-6:]
print("== Admin sin 2FA")
s, b, _ = login(ADMIN_USER, ADMIN_PASS)
check(s == 200 and b["access_token"] and b["mfa"] == {"habilitado": True, "activo": False}, "login sólo con clave", (s, b))
adm = b["access_token"]
s, b, _ = gw("POST", "/api/security/users", {"username": f"e2e{suf}", "email": f"e2e{suf}@e2e.local",
                                              "password": "ClaveE2E-1234", "full_name": "E2E"}, adm)
check(s == 403 and b["code"] == "2fa_requerido", "operación sensible sin 2FA: 403 2fa_requerido", (s, b))

print("== Enrolamiento del admin")
en, act = enrolar_y_activar(adm)
secret = en["secret"]
check("issuer=" in en["otpauth_uri"] and urllib.parse.quote(ADMIN_USER) in en["otpauth_uri"],
      "otpauth con issuer del tenant y el username como cuenta", en["otpauth_uri"])
check(len(act["recovery_codes"]) == 10, "10 códigos de recuperación")
codigos = act["recovery_codes"]
s, _, _ = gw("GET", "/api/auth/2fa/estado", token=adm)
check(s == 401, "la sesión anterior quedó revocada")
adm = act["access_token"]
s, est, _ = gw("GET", "/api/auth/2fa/estado", token=adm)
check(s == 200 and est["activo"] and est["sesion_con_2fa"], "estado: activo y sesión con 2FA", est)

s, me, _ = gw("GET", "/api/security/users?per_page=500", token=adm)
admin_id = next(u["id"] for u in me["data"] if u["username"] == ADMIN_USER)
s, toks, _ = req("GET", f"{TS}/users/{admin_id}/tokens", headers={"Authorization": f"Bearer {TS_KEY}"})
check(s == 200 and any(t["status"] == "active" for t in toks["tokens"]),
      "en TokenServer el uid es el id interno del usuario", (admin_id, toks))

print("== Step-up")
nuevo = {"username": f"e2e{suf}", "email": f"e2e{suf}@e2e.local", "password": "ClaveE2E-1234", "full_name": "E2E"}
s, b, _ = gw("POST", "/api/security/users", nuevo, adm)
check(s == 403 and b["code"] == "step_up_requerido" and b["operacion"] == "Crear un usuario", "pide step-up", (s, b))
s, b, _ = gw("POST", "/api/auth/2fa/step-up", {"code": "000000"}, adm)
check(s == 422 and b["code"] == "codigo_invalido" and "remaining_attempts" in b, "step-up con código malo: 422", (s, b))
s, su, _ = gw("POST", "/api/auth/2fa/step-up", {"code": codigo_nuevo(secret)}, adm)
check(s == 200 and su["expires_in"] == 300, "step-up con el código: token de 5 minutos", (s, su))
H = {"X-2FA-Token": su["step_up_token"]}
s, u1, _ = gw("POST", "/api/security/users", nuevo, adm, H)
check(s == 201, "con X-2FA-Token la operación pasa", (s, u1))
nuevo2 = {**nuevo, "username": f"e2f{suf}", "email": f"e2f{suf}@e2e.local"}
s, u2, _ = gw("POST", "/api/security/users", nuevo2, adm, H)
check(s == 201, "el step-up se reusa mientras dura (sin pedir otro código)", (s, u2))
s, b, _ = gw("POST", "/api/security/users", {**nuevo, "username": f"e2g{suf}", "email": f"e2g{suf}@e2e.local"},
             adm, {"X-2FA-Token": su["step_up_token"][:-3] + "abc"})
check(s == 403 and b["code"] == "step_up_requerido", "un step-up adulterado no sirve")

print("== Login con 2FA")
s, b, _ = gw("POST", "/api/auth/logout", token=adm)
s, b, _ = login(ADMIN_USER, ADMIN_PASS)
check(s == 200 and b["requires_2fa"] and b["access_token"] is None and b["mfa_token"], "la clave sola no da sesión", b)
mfa = b["mfa_token"]
s, b, _ = gw("GET", "/api/auth/2fa/estado", token=mfa)
check(s == 401, "el token temporal no sirve como sesión")
s, b, _ = gw("POST", "/api/auth/2fa/login", {"mfa_token": mfa, "code": "000000"})
check(s == 422 and b["remaining_attempts"] >= 1, "código incorrecto: 422 con intentos restantes", (s, b))
s, b, _ = gw("POST", "/api/auth/2fa/login", {"mfa_token": mfa, "code": codigo_nuevo(secret)})
check(s == 200 and b["access_token"], "código correcto: sesión", (s, b))
adm = b["access_token"]
s, b, _ = gw("POST", "/api/auth/2fa/login", {"mfa_token": mfa, "code": codigo_nuevo(secret)})
check(s == 400 and b["code"] == "mfa_token_invalido", "el token temporal es de un solo uso", (s, b))

s, b, _ = login(ADMIN_USER, ADMIN_PASS)
s, b, _ = gw("POST", "/api/auth/2fa/login", {"mfa_token": b["mfa_token"], "code": codigos[0].lower()})
check(s == 200 and b["remaining_recovery_codes"] == 9, "login con código de recuperación", (s, b))
adm = b["access_token"]

print("== Bloqueo y reset por admin")
# Un usuario sin ningún permiso no pasa el gateway: se le da un rol (con step-up, es un cambio de permisos).
s, roles, _ = gw("GET", "/api/security/roles", token=adm)
rol = next((r for r in roles if r["name"] != "admin"), roles[0])
s, su, _ = gw("POST", "/api/auth/2fa/step-up", {"code": codigo_nuevo(secret)}, adm)
s, b, _ = gw("POST", f"/api/security/users/{u1['id']}/roles", {"role_ids": [rol["id"]]}, adm,
             {"X-2FA-Token": su["step_up_token"]})
check(s == 200, f"asignar el rol {rol['name']} (con step-up)", (s, b))
s, b, _ = login(nuevo["username"], nuevo["password"])
op = b["access_token"]
en2, act2 = enrolar_y_activar(op)
s, b, _ = login(nuevo["username"], nuevo["password"])
mfa2 = b["mfa_token"]
estado = None
for _ in range(12):
    s, b, h = gw("POST", "/api/auth/2fa/login", {"mfa_token": mfa2, "code": "000000"})
    if s == 429:
        estado = (s, b, h)
        break
check(estado and estado[1]["code"] == "2fa_bloqueado" and estado[2].get("retry-after"),
      "tras varios códigos malos: 429 con Retry-After", estado)
s, b, _ = gw("POST", "/api/auth/2fa/login", {"mfa_token": mfa2, "code": codigo_nuevo(en2["secret"])})
check(s == 429, "bloqueado, ni el código correcto pasa")
s, b, _ = gw("DELETE", f"/api/security/users/{u1['id']}/2fa", token=adm)
check(s == 403 and b["code"] == "step_up_requerido", "el reset también pide step-up", (s, b))
s, su, _ = gw("POST", "/api/auth/2fa/step-up", {"code": codigo_nuevo(secret)}, adm)
s, b, _ = gw("DELETE", f"/api/security/users/{u1['id']}/2fa", token=adm, headers={"X-2FA-Token": su["step_up_token"]})
check(s == 200 and b["totp_activo"] is False and b["dispositivos_borrados"] >= 1, "reset del 2FA por el admin", (s, b))
s, b, _ = login(nuevo["username"], nuevo["password"])
check(s == 200 and b["access_token"], "después del reset entra sólo con clave (y puede re-enrolarse)", b)
s, b, _ = gw("DELETE", f"/api/security/users/{admin_id}/2fa", token=adm, headers={"X-2FA-Token": su["step_up_token"]})
check(s == 403, "nadie resetea su propio 2FA")

if SIN_TS:
    print("== TokenServer caído (falla cerrado)")
    s, b, _ = req("POST", SIN_TS + "/api/auth/login", {"username": ADMIN_USER, "password": ADMIN_PASS})
    t0 = time.time()
    s, b, _ = req("POST", SIN_TS + "/api/auth/2fa/login", {"mfa_token": b["mfa_token"], "code": totp(secret)})
    check(s == 503 and b["code"] == "2fa_no_disponible" and "access_token" not in b,
          "sin TokenServer, quien tiene 2FA no entra (503)", (s, b))
    check(time.time() - t0 < 6, "y falla rápido (timeout corto)", round(time.time() - t0, 2))

print("== Desactivar")
s, b, _ = gw("POST", "/api/auth/2fa/desactivar", {"code": "000000"}, adm)
check(s == 422, "desactivar exige un código válido")
s, b, _ = gw("POST", "/api/auth/2fa/desactivar", {"code": codigo_nuevo(secret)}, adm)
check(s == 200 and b["access_token"], "desactivar con código", (s, b))
s, b, _ = login(ADMIN_USER, ADMIN_PASS)
check(s == 200 and b["access_token"], "el admin vuelve a entrar sólo con clave")

print(f"\nE2E OK: {ok} verificaciones")
