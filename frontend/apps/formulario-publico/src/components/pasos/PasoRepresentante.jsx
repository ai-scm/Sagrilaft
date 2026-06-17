import { useMemo } from 'react';
import FormField from '../FormField';
import LocationSelect from '../LocationSelect';
import NacionalidadSelect from '../NacionalidadSelect';
import AlertasInconsistencia from '../AlertasInconsistencia';
import { useUbicacion, NA_OPTION } from '../../hooks/useUbicacion';

const TIPOS_DOC = [
  { value: 'CC',  label: 'Cédula de Ciudadanía' },
  { value: 'CE',  label: 'Cédula de Extranjería' },
  { value: 'PAS', label: 'Pasaporte'             },
];

/**
 * Paso 3 — Identidad del Sujeto Obligado / Representante Legal.
 *
 * Reutiliza useUbicacion (País → Departamento → Ciudad) solo en el bloque
 * del lugar donde ejerce funciones. La ciudad de residencia quedó como texto
 * libre para permitir cualquier valor sin depender del país seleccionado.
 *
 * Ciudad de Expedición y Ciudad de Nacimiento son campos de texto libre;
 * no usan selección jerárquica.
 */
export default function PasoRepresentante({ formData, onChange, onOpenHelp, errors, alertasNombreRepresentante, alertasNumeroDocRepresentante }) {
  const esNatural = formData.tipo_persona === 'natural';

  // Fecha máxima para date pickers: calculada por instancia, no por importación
  const today = useMemo(() => new Date().toISOString().split('T')[0], []);

  // Elimina la repetición de value/onChange/onOpenHelp/error en cada FormField
  const fieldProps = (name) => ({ name, value: formData[name], onChange, onOpenHelp, error: errors[name] });

  // ── Bloque 1: Ciudad donde ejerce funciones ──────────────────────────────────
  const {
    paisesOptions:        paisesFuncionesOptions,
    departamentosOptions: departamentosFuncionesOptions,
    ciudadesOptions:      ciudadesFuncionesOptions,
    selectedPais:         selectedPaisFunciones,
    selectedDepartamento: selectedDepartamentoFunciones,
    selectedCiudad:       selectedCiudadFunciones,
    paisSinDepartamentos: paisesFuncionesSinDepartamentos,
    departamentoSinCiudades: departamentoFuncionesSinCiudades,
    handlePaisChange:         handlePaisFuncionesChange,
    handleDepartamentoChange: handleDepartamentoFuncionesChange,
    handleCiudadChange:       handleCiudadFuncionesChange,
  } = useUbicacion(formData, onChange, {
    paisKey:         'pais_funciones',
    departamentoKey: 'departamento_funciones',
    ciudadKey:       'ciudad_funciones',
  });

  return (
    <div className="form-card">
      <h2 className="section-title">INFORMACION REPRESENTANTE LEGAL O PERSONA NATURAL</h2>
      <p className="section-subtitle">
        {esNatural
          ? 'Información de la persona natural'
          : 'Datos del representante legal de la empresa o Persona Natural'}
      </p>

      {/* ── Nombre e identificación ─────────────────────────────────────────── */}
      <div className="form-row single">
        <FormField label="Nombres y Apellidos" required {...fieldProps('nombre_representante')} />
      </div>

      <AlertasInconsistencia alertas={alertasNombreRepresentante} tipoCampo="nombre del representante sin resolver" nombreCampo="Nombres y Apellidos" />

      <div className="form-row">
        <FormField label="Tipo de Documento" type="select" required options={TIPOS_DOC} {...fieldProps('tipo_doc_representante')} />
        <FormField label="No. de Identificación" required {...fieldProps('numero_doc_representante')} />
      </div>

      <AlertasInconsistencia alertas={alertasNumeroDocRepresentante} tipoCampo="No. de Identificación del representante sin resolver" nombreCampo="No. de Identificación" />

      {/* ── Fecha de expedición ─────────────────────────────────────────────── */}
      <div className="form-row">
        <FormField label="Fecha de Expedición" type="date" required max={today} {...fieldProps('fecha_expedicion')} />
      </div>

      {/* ── Ciudad de Expedición ─────────────────────────────────────────────── */}
      <div className="form-row">
        <FormField label="Ciudad de Expedición" required {...fieldProps('ciudad_expedicion')} />
      </div>

      {/* ── Nacionalidad y fecha de nacimiento ──────────────────────────────── */}
      <div className="form-row">
        <NacionalidadSelect required value={formData.nacionalidad} onChange={onChange} onOpenHelp={onOpenHelp} error={errors.nacionalidad} />
        <FormField label="Fecha de Nacimiento" type="date" required max={today} {...fieldProps('fecha_nacimiento')} />
      </div>

      {/* ── Ciudad de Nacimiento ─────────────────────────────────────────────── */}
      <div className="form-row">
        <FormField label="Ciudad de Nacimiento" required {...fieldProps('ciudad_nacimiento')} />
      </div>

      {/* ── Profesión y contacto ────────────────────────────────────────────── */}
      <div className="form-row">
        <FormField label="Profesión" required {...fieldProps('profesion')} />
        <FormField label="Correo Electrónico" type="email" required {...fieldProps('correo_representante')} />
        <FormField label="Teléfono" type="tel" required {...fieldProps('telefono_representante')} />
      </div>

      {/* ── Dirección y ciudad donde ejerce funciones ───────────────────────── */}
      <div className="form-row single">
        <FormField label="Dirección donde ejerce funciones" required {...fieldProps('direccion_funciones')} />
      </div>

      {/* ── Lugar donde ejerce funciones (País → Departamento → Ciudad) ─────── */}
      <div className="form-row">
        <LocationSelect
          label="País (Funciones)" name="pais_funciones" required
          value={selectedPaisFunciones}
          onChange={handlePaisFuncionesChange}
          options={paisesFuncionesOptions}
          onOpenHelp={onOpenHelp} error={errors.pais_funciones}
        />
        <LocationSelect
          label="Departamento (Funciones)" name="departamento_funciones" required
          value={paisesFuncionesSinDepartamentos ? NA_OPTION : selectedDepartamentoFunciones}
          onChange={handleDepartamentoFuncionesChange}
          options={departamentosFuncionesOptions}
          disabled={!formData.pais_funciones || paisesFuncionesSinDepartamentos}
          onOpenHelp={onOpenHelp} error={errors.departamento_funciones}
        />
        <LocationSelect
          label="Ciudad donde ejerce funciones" name="ciudad_funciones" required
          value={paisesFuncionesSinDepartamentos || departamentoFuncionesSinCiudades ? NA_OPTION : selectedCiudadFunciones}
          onChange={handleCiudadFuncionesChange}
          options={ciudadesFuncionesOptions}
          disabled={!formData.departamento_funciones || paisesFuncionesSinDepartamentos || departamentoFuncionesSinCiudades}
          onOpenHelp={onOpenHelp} error={errors.ciudad_funciones}
        />
      </div>

      {/* ── Residencia libre (solo persona natural) ─────────────────────────── */}
      {esNatural && (
        <>
          <div className="form-row single">
            <FormField label="Dirección de Residencia (SOLO PARA PERSONA NATURAL)" required {...fieldProps('direccion_residencia')} />
          </div>

          <div className="form-row">
            <FormField
              label="Ciudad de Residencia"
              name="ciudad_residencia"
              required
              value={formData.ciudad_residencia}
              onChange={onChange}
              onOpenHelp={onOpenHelp}
              error={errors.ciudad_residencia}
            />
          </div>
        </>
      )}
    </div>
  );
}
