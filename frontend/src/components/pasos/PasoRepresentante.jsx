import { useMemo } from 'react';
import { City } from 'country-state-city';
import FormField from '../FormField';
import LocationSelect from '../LocationSelect';
import NacionalidadSelect from '../NacionalidadSelect';
import AlertasInconsistencia from '../AlertasInconsistencia';
import { useUbicacion } from '../../hooks/useUbicacion';

const TIPOS_DOC = [
  { value: 'CC',  label: 'Cédula de Ciudadanía' },
  { value: 'CE',  label: 'Cédula de Extranjería' },
  { value: 'PAS', label: 'Pasaporte'             },
];

// Fecha máxima permitida para date pickers: hoy (no fechas futuras)
const today = new Date().toISOString().split('T')[0];

/**
 * Paso 3 — Identidad del Sujeto Obligado / Representante Legal.
 *
 * Reutiliza useUbicacion (País → Departamento → Ciudad) en dos bloques:
 *   1. Ciudad donde ejerce funciones
 *   2. Ciudad de residencia (solo persona natural)
 *
 * Ciudad de Expedición y Ciudad de Nacimiento son campos de texto libre;
 * no usan selección jerárquica.
 */
export default function PasoRepresentante({ formData, onChange, onOpenHelp, errors, alertasNombreRepresentante, alertasNumeroDocRepresentante }) {
  const esNatural  = formData.tipo_persona === 'natural';
  const defaultPais = formData.pais || '';

  // ── Bloque 1: Ciudad donde ejerce funciones ──────────────────────────────────
  const ubFunciones = useUbicacion(formData, onChange, {
    paisKey:         'pais_funciones',
    departamentoKey: 'departamento_funciones',
    ciudadKey:       'ciudad_funciones',
    defaultPais,
  });

  // ── Bloque 2: Ciudad de Residencia (todas las ciudades del país, sin filtro) ─
  const ciudadesResidencia = useMemo(
    () => City.getCitiesOfCountry(defaultPais || 'CO').map(c => ({ value: c.name, label: c.name })),
    [defaultPais],
  );
  const selectedCiudadResidencia = ciudadesResidencia.find(o => o.value === formData.ciudad_residencia) ?? null;
  const handleCiudadResidenciaChange = (option) =>
    onChange({ target: { name: 'ciudad_residencia', value: option?.value ?? '', type: 'text' } });

  return (
    <div className="form-card">
      <h2 className="section-title">INFORMACION REPRESENTANTE LEGAL O PERSONA NATURAL</h2>
      <p className="section-subtitle">
        {esNatural
          ? 'Información de la persona natural'
          : 'Datos del representante legal de la empresa'}
      </p>

      {/* ── Nombre e identificación ─────────────────────────────────────────── */}
      <div className="form-row single">
        <FormField
          label="Nombres y Apellidos" name="nombre_representante" required
          value={formData.nombre_representante} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.nombre_representante}
        />
      </div>

      <AlertasInconsistencia alertas={alertasNombreRepresentante} tipoCampo="nombre del representante sin resolver" nombreCampo="Nombres y Apellidos" />

      <div className="form-row">
        <FormField
          label="Tipo de Documento" name="tipo_doc_representante" type="select" required
          value={formData.tipo_doc_representante} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.tipo_doc_representante}
          options={TIPOS_DOC}
        />
        <FormField
          label="No. de Identificación" name="numero_doc_representante" required
          value={formData.numero_doc_representante} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.numero_doc_representante}
        />
      </div>

      <AlertasInconsistencia alertas={alertasNumeroDocRepresentante} tipoCampo="No. de Identificación del representante sin resolver" nombreCampo="No. de Identificación" />

      {/* ── Fecha de expedición ─────────────────────────────────────────────── */}
      <div className="form-row">
        <FormField
          label="Fecha de Expedición" name="fecha_expedicion" type="date" required
          value={formData.fecha_expedicion} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.fecha_expedicion}
          max={today}
        />
      </div>

      {/* ── Ciudad de Expedición ─────────────────────────────────────────────── */}
      <div className="form-row">
        <FormField
          label="Ciudad de Expedición" name="ciudad_expedicion" required
          value={formData.ciudad_expedicion} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.ciudad_expedicion}
        />
      </div>

      {/* ── Nacionalidad y fecha de nacimiento ──────────────────────────────── */}
      <div className="form-row">
        <NacionalidadSelect
          required
          value={formData.nacionalidad} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.nacionalidad}
        />
        <FormField
          label="Fecha de Nacimiento" name="fecha_nacimiento" type="date" required
          value={formData.fecha_nacimiento} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.fecha_nacimiento}
          max={today}
        />
      </div>

      {/* ── Ciudad de Nacimiento ─────────────────────────────────────────────── */}
      <div className="form-row">
        <FormField
          label="Ciudad de Nacimiento" name="ciudad_nacimiento" required
          value={formData.ciudad_nacimiento} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.ciudad_nacimiento}
        />
      </div>

      {/* ── Profesión y contacto ────────────────────────────────────────────── */}
      <div className="form-row">
        <FormField
          label="Profesión" name="profesion" required
          value={formData.profesion} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.profesion}
        />
        <FormField
          label="Correo Electrónico" name="correo_representante" type="email" required
          value={formData.correo_representante} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.correo_representante}
        />
        <FormField
          label="Teléfono" name="telefono_representante" type="tel" required
          value={formData.telefono_representante} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.telefono_representante}
        />
      </div>

      {/* ── Dirección y ciudad donde ejerce funciones ───────────────────────── */}
      <div className="form-row single">
        <FormField
          label="Dirección donde ejerce funciones" name="direccion_funciones" required
          value={formData.direccion_funciones} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.direccion_funciones}
        />
      </div>

      {/* ── Lugar donde ejerce funciones (País → Departamento → Ciudad) ─────── */}
      <div className="form-row">
        <LocationSelect
          label="País (Funciones)" name="pais_funciones"
          value={ubFunciones.selectedPais}
          onChange={ubFunciones.handlePaisChange}
          options={ubFunciones.paisesOptions}
          onOpenHelp={onOpenHelp}
        />
        <LocationSelect
          label="Departamento (Funciones)" name="departamento_funciones"
          value={ubFunciones.selectedDepartamento}
          onChange={ubFunciones.handleDepartamentoChange}
          options={ubFunciones.departamentosOptions}
          disabled={!ubFunciones.selectedPais}
          onOpenHelp={onOpenHelp}
        />
        <LocationSelect
          label="Ciudad donde ejerce funciones" name="ciudad_funciones" required
          value={ubFunciones.selectedCiudad}
          onChange={ubFunciones.handleCiudadChange}
          options={ubFunciones.ciudadesOptions}
          disabled={!ubFunciones.selectedDepartamento}
          onOpenHelp={onOpenHelp} error={errors.ciudad_funciones}
        />
      </div>

      {/* ── Residencia (solo persona natural) ───────────────────────────────── */}
      {esNatural && (
        <>
          <div className="form-row single">
            <FormField
              label="Dirección de Residencia (SOLO PARA PERSONA NATURAL)" name="direccion_residencia"
              value={formData.direccion_residencia} onChange={onChange}
              onOpenHelp={onOpenHelp}
            />
          </div>

          <div className="form-row">
            <LocationSelect
              label="Ciudad de Residencia" name="ciudad_residencia" required
              value={selectedCiudadResidencia}
              onChange={handleCiudadResidenciaChange}
              options={ciudadesResidencia}
              onOpenHelp={onOpenHelp} error={errors.ciudad_residencia}
            />
          </div>
        </>
      )}
    </div>
  );
}
