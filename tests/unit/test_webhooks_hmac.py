"""
Normalizacion de la firma HMAC del webhook de ZohoSign.

Bug real encontrado en staging (2026-09-24): la firma real que envia Zoho
viene en base64 (ej. "hy020yEBItdvapBhjuQCdg07XQBRiDxyyWc9rqhR1nc="), que
casi siempre termina en "=" de padding. _normalizar_firma recortaba
cualquier cosa despues del ultimo "=", dejando la firma vacia y
rechazando siempre el webhook real (403), aunque el secreto configurado
era correcto. El test existente de integracion (test_expediente_webhook_
zoho.py) firma con hexdigest() y nunca ejercia esta rama, por eso no se
detecto en CI.
"""
import base64
import hashlib
import hmac

from api.routers.webhooks import _firmas_esperadas, _normalizar_firma

_SECRETO = "zoho-webhook-test"
_CUERPO = b'{"requests":{"request_id":"123"}}'


def _firma_base64(secreto: str, cuerpo: bytes) -> str:
    digest = hmac.new(secreto.encode("utf-8"), cuerpo, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def _firma_hex(secreto: str, cuerpo: bytes) -> str:
    return hmac.new(secreto.encode("utf-8"), cuerpo, hashlib.sha256).hexdigest()


def test_normalizar_firma_no_destruye_base64_con_padding():
    firma_base64 = _firma_base64(_SECRETO, _CUERPO)
    assert firma_base64.endswith("=")  # caso real observado en staging

    normalizada = _normalizar_firma(firma_base64)

    assert normalizada == firma_base64
    assert normalizada in _firmas_esperadas(_CUERPO, _SECRETO)


def test_normalizar_firma_mantiene_hex_intacta():
    firma_hex = _firma_hex(_SECRETO, _CUERPO)

    normalizada = _normalizar_firma(firma_hex)

    assert normalizada == firma_hex
    assert normalizada in _firmas_esperadas(_CUERPO, _SECRETO)


def test_normalizar_firma_quita_prefijo_sha256():
    firma_hex = _firma_hex(_SECRETO, _CUERPO)

    normalizada = _normalizar_firma(f"sha256={firma_hex}")

    assert normalizada == firma_hex


def test_normalizar_firma_rechaza_secreto_incorrecto():
    firma_base64 = _firma_base64("secreto-equivocado", _CUERPO)

    normalizada = _normalizar_firma(firma_base64)

    assert normalizada not in _firmas_esperadas(_CUERPO, _SECRETO)
