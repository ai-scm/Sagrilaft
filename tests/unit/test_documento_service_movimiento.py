from domain.constantes import TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT
from domain.contratos import DocumentoDatos
from services.formulario.documento_service import DocumentoService


class _RepoDocumentoFake:
    def __init__(self, documentos: list[DocumentoDatos]):
        self._documentos = documentos
        self.rutas_actualizadas: dict[str, str] | None = None

    def listar_activos(self, formulario_id: str) -> list[DocumentoDatos]:
        return self._documentos

    def actualizar_rutas(self, rutas: dict[str, str]) -> None:
        self.rutas_actualizadas = rutas


class _StorageFake:
    def __init__(self, existentes: set[str]):
        self._existentes = set(existentes)
        self.movimientos: list[tuple[str, str]] = []
        self.prefijos_limpiados: list[str] = []

    def existe(self, key: str) -> bool:
        return key in self._existentes

    def mover(self, key_origen: str, key_destino: str) -> None:
        self.movimientos.append((key_origen, key_destino))

    def limpiar_directorio_vacio(self, key: str) -> None:
        self.prefijos_limpiados.append(key)


def test_mover_archivos_omite_certificado_sagrilaft_temporal():
    formulario_id = "f-1"
    repo = _RepoDocumentoFake([
        DocumentoDatos(
            id="doc-1",
            formulario_id=formulario_id,
            tipo_documento="rut",
            nombre_archivo="rut.pdf",
            ruta_archivo="tmp/SAG-1/rut.pdf",
        ),
        DocumentoDatos(
            id="doc-2",
            formulario_id=formulario_id,
            tipo_documento=TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
            nombre_archivo="certificado_sagrilaft.pdf",
            ruta_archivo="/tmp/certificado_sagrilaft.pdf",
        ),
    ])
    storage = _StorageFake({"tmp/SAG-1/rut.pdf"})
    service = DocumentoService(repo, storage)

    service.mover_archivos_formulario_a_contraparte(formulario_id, "CLIENTES/EMPRESA")

    assert storage.movimientos == [("tmp/SAG-1/rut.pdf", "CLIENTES/EMPRESA/rut.pdf")]
    assert repo.rutas_actualizadas == {"doc-1": "CLIENTES/EMPRESA/rut.pdf"}
    assert storage.prefijos_limpiados == ["tmp/SAG-1"]


def test_mover_archivos_omite_origen_inexistente_sin_romper_envio():
    formulario_id = "f-1"
    repo = _RepoDocumentoFake([
        DocumentoDatos(
            id="doc-1",
            formulario_id=formulario_id,
            tipo_documento="rut",
            nombre_archivo="rut.pdf",
            ruta_archivo="tmp/SAG-1/rut.pdf",
        ),
    ])
    storage = _StorageFake(set())
    service = DocumentoService(repo, storage)

    service.mover_archivos_formulario_a_contraparte(formulario_id, "CLIENTES/EMPRESA")

    assert storage.movimientos == []
    assert repo.rutas_actualizadas is None
    assert storage.prefijos_limpiados == ["tmp/SAG-1"]
