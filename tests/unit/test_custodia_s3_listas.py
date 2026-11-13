"""Custodia S3 de listas y selección por entorno. Sin red: cliente S3 en memoria."""
import hashlib

import pytest

from domain.listas.errores import ErrorIntegridadEvidencia
from infrastructure.listas.custodia import CustodiaLocalListas, CustodiaS3Listas, custodia_desde_entorno


class S3EnMemoria:
    def __init__(self):
        self.objetos, self.escrituras = {}, []

    def put_object(self, **argumentos):
        self.escrituras.append(argumentos)
        self.objetos[(argumentos["Bucket"], argumentos["Key"])] = argumentos["Body"]

    def get_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objetos:
            raise KeyError("NoSuchKey")
        contenido = self.objetos[(Bucket, Key)]

        class Cuerpo:
            def read(self):
                return contenido
        return {"Body": Cuerpo()}


def test_guarda_por_huella_bajo_su_prefijo_y_lee_verificando():
    s3 = S3EnMemoria()
    custodia = CustodiaS3Listas("bucket-pruebas", cliente=s3)
    objeto = custodia.guardar(b"%PDF-1.4 informe")
    huella = hashlib.sha256(b"%PDF-1.4 informe").hexdigest()
    assert objeto.clave == objeto.huella == huella and objeto.tamano_bytes == 16
    escritura = s3.escrituras[0]
    assert escritura["Key"] == f"listas/custodia/{huella}" and escritura["ServerSideEncryption"] == "AES256"
    assert custodia.leer(huella, huella, 16) == b"%PDF-1.4 informe"


def test_rechaza_claves_ajenas_contenido_alterado_y_objetos_ausentes():
    s3 = S3EnMemoria()
    custodia = CustodiaS3Listas("bucket-pruebas", cliente=s3)
    objeto = custodia.guardar(b"original")
    with pytest.raises(ErrorIntegridadEvidencia):
        custodia.leer("../otro", "../otro")
    s3.objetos[("bucket-pruebas", f"listas/custodia/{objeto.clave}")] = b"alterado"
    with pytest.raises(ErrorIntegridadEvidencia):
        custodia.leer(objeto.clave, objeto.huella)
    with pytest.raises(ErrorIntegridadEvidencia):
        custodia.leer("a" * 64, "a" * 64)


@pytest.mark.parametrize("prefijo", ["sin-barra", "/absoluto/"])
def test_prefijo_invalido(prefijo):
    with pytest.raises(ValueError):
        CustodiaS3Listas("bucket", prefijo, cliente=S3EnMemoria())


def test_seleccion_por_entorno(monkeypatch, tmp_path):
    for variable in ("LISTAS_CUSTODIA_BACKEND", "LISTAS_CUSTODIA_DIRECTORIO", "S3_BUCKET"):
        monkeypatch.delenv(variable, raising=False)
    assert custodia_desde_entorno() is None
    monkeypatch.setenv("LISTAS_CUSTODIA_DIRECTORIO", str(tmp_path / "custodia"))
    assert isinstance(custodia_desde_entorno(), CustodiaLocalListas)
    monkeypatch.setenv("LISTAS_CUSTODIA_BACKEND", "s3")
    with pytest.raises(ValueError, match="bucket"):
        custodia_desde_entorno()
    monkeypatch.setenv("S3_BUCKET", "bucket-staging")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    custodia = custodia_desde_entorno()
    assert isinstance(custodia, CustodiaS3Listas) and custodia.bucket == "bucket-staging"
    monkeypatch.setenv("LISTAS_CUSTODIA_BACKEND", "disco")
    with pytest.raises(ValueError):
        custodia_desde_entorno()
