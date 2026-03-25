import { useMemo } from 'react';
import { City } from 'country-state-city';
import FormField from '../FormField';
import LocationSelect from '../LocationSelect';
import NacionalidadSelect from '../NacionalidadSelect';
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
 * Reutiliza useUbicacion (País → Departamento → Ciudad) en cuatro bloques:
 *   1. Lugar de expedición del documento
 *   2. Lugar de nacimiento
 *   3. Ciudad donde ejerce funciones
 *   4. Ciudad de residencia (solo persona natural)
 *
 * Cada bloque hereda el país de la empresa como valor por defecto,
 * pero el usuario puede cambiarlo de forma independiente.
 */
export default function PasoRepresentante({ formData, onChange, onOpenHelp, errors }) {
  const esNatural  = formData.tipo_persona === 'natural';
  const defaultPais = formData.pais || '';

  // ── Bloque 1: Ciudad de Expedición ──────────────────────────────────────────
  const ubExpedicion = useUbicacion(formData, onChange, {
    paisKey:         'pais_expedicion',
    departamentoKey: 'departamento_expedicion',
    ciudadKey:       'ciudad_expedicion',
    defaultPais,
  });

  // ── Bloque 2: Ciudad de Nacimiento ──────────────────────────────────────────
  const ubNacimiento = useUbicacion(formData, onChange, {
    paisKey:         'pais_nacimiento',
    departamentoKey: 'departamento_nacimiento',
    ciudadKey:       'ciudad_nacimiento',
    defaultPais,
  });

  // ── Bloque 3: Ciudad donde ejerce funciones ──────────────────────────────────
  const ubFunciones = useUbicacion(formData, onChange, {
    paisKey:         'pais_funciones',
    departamentoKey: 'departamento_funciones',
    ciudadKey:       'ciudad_funciones',
    defaultPais,
  });

  // ── Ciudad de Residencia: todas las ciudades del país (sin filtro departamento) ─
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

      {/* ── Fecha de expedición ─────────────────────────────────────────────── */}
      <div className="form-row">
        <FormField
          label="Fecha de Expedición" name="fecha_expedicion" type="date" required
          value={formData.fecha_expedicion} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.fecha_expedicion}
          max={today}
        />
      </div>

      {/* ── Lugar de expedición (País → Departamento → Ciudad) ──────────────── */}
      <div className="form-row">
        <LocationSelect
          label="País de Expedición" name="pais_expedicion"
          value={ubExpedicion.selectedPais}
          onChange={ubExpedicion.handlePaisChange}
          options={ubExpedicion.paisesOptions}
          onOpenHelp={onOpenHelp}
        />
        <LocationSelect
          label="Departamento de Expedición" name="departamento_expedicion" required
          value={ubExpedicion.selectedDepartamento}
          onChange={ubExpedicion.handleDepartamentoChange}
          options={ubExpedicion.departamentosOptions}
          onOpenHelp={onOpenHelp} error={errors.departamento_expedicion}
        />
        <LocationSelect
          label="Ciudad de Expedición" name="ciudad_expedicion" required
          value={ubExpedicion.selectedCiudad}
          onChange={ubExpedicion.handleCiudadChange}
          options={ubExpedicion.ciudadesOptions}
          disabled={!ubExpedicion.selectedDepartamento}
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

      {/* ── Lugar de nacimiento (País → Departamento → Ciudad) ──────────────── */}
      <div className="form-row">
        <LocationSelect
          label="País de Nacimiento" name="pais_nacimiento"
          value={ubNacimiento.selectedPais}
          onChange={ubNacimiento.handlePaisChange}
          options={ubNacimiento.paisesOptions}
          onOpenHelp={onOpenHelp}
        />
        <LocationSelect
          label="Departamento de Nacimiento" name="departamento_nacimiento"
          value={ubNacimiento.selectedDepartamento}
          onChange={ubNacimiento.handleDepartamentoChange}
          options={ubNacimiento.departamentosOptions}
          disabled={!ubNacimiento.selectedPais}
          onOpenHelp={onOpenHelp}
        />
        <LocationSelect
          label="Ciudad de Nacimiento" name="ciudad_nacimiento" required
          value={ubNacimiento.selectedCiudad}
          onChange={ubNacimiento.handleCiudadChange}
          options={ubNacimiento.ciudadesOptions}
          disabled={!ubNacimiento.selectedDepartamento}
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
