import FormField from '../FormField';

const TIPOS_DOC = [
  { value: 'CC',  label: 'Cédula de Ciudadanía' },
  { value: 'CE',  label: 'Cédula de Extranjería' },
  { value: 'PAS', label: 'Pasaporte'             },
];

/**
 * Paso 3 — Identidad del Sujeto Obligado / Representante Legal.
 * Para Persona Natural muestra campos de residencia adicionales.
 */
export default function PasoRepresentante({ formData, onChange, onOpenHelp, errors }) {
  const esNatural = formData.tipo_persona === 'natural';

  return (
    <div className="form-card">
      <h2 className="section-title">👤 Representante Legal</h2>
      <p className="section-subtitle">
        {esNatural
          ? 'Información de la persona natural'
          : 'Datos del representante legal de la empresa'}
      </p>

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

      <div className="form-row">
        <FormField
          label="Fecha de Expedición" name="fecha_expedicion" type="date" required
          value={formData.fecha_expedicion} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.fecha_expedicion}
        />
        <FormField
          label="Ciudad de Expedición" name="ciudad_expedicion" required
          value={formData.ciudad_expedicion} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.ciudad_expedicion}
        />
      </div>

      <div className="form-row">
        <FormField
          label="Nacionalidad" name="nacionalidad" required
          value={formData.nacionalidad} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.nacionalidad}
        />
        <FormField
          label="Fecha de Nacimiento" name="fecha_nacimiento" type="text" required
          placeholder="Ej: 15-AGO-1990"
          value={formData.fecha_nacimiento} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.fecha_nacimiento}
        />
        <FormField
          label="Ciudad de Nacimiento" name="ciudad_nacimiento" required
          value={formData.ciudad_nacimiento} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.ciudad_nacimiento}
        />
      </div>

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

      <div className="form-row">
        <FormField
          label="Dirección donde ejerce funciones" name="direccion_funciones" required
          value={formData.direccion_funciones} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.direccion_funciones}
        />
        <FormField
          label="Ciudad" name="ciudad_funciones" required
          value={formData.ciudad_funciones} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.ciudad_funciones}
        />
      </div>

      {esNatural && (
        <div className="form-row">
          <FormField
            label="Dirección de Residencia" name="direccion_residencia"
            value={formData.direccion_residencia} onChange={onChange}
            onOpenHelp={onOpenHelp}
          />
          <FormField
            label="Ciudad de Residencia" name="ciudad_residencia"
            value={formData.ciudad_residencia} onChange={onChange}
            onOpenHelp={onOpenHelp}
          />
        </div>
      )}
    </div>
  );
}
