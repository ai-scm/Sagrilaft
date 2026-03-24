import FormField from '../FormField';

const TIPOS_CONTRAPARTE = [
  { value: 'proveedor', label: 'Proveedor' },
  { value: 'cliente',   label: 'Cliente'   },
];

const TIPOS_PERSONA = [
  { value: 'juridica', label: 'Persona Jurídica' },
  { value: 'natural',  label: 'Persona Natural'  },
];

const TIPOS_SOLICITUD = [
  { value: 'vinculacion',  label: 'Vinculación'  },
  { value: 'actualizacion', label: 'Actualización' },
];

const TIPOS_IDENTIFICACION = [
  { value: 'NIT', label: 'NIT'                  },
  { value: 'CC',  label: 'Cédula de Ciudadanía' },
  { value: 'CE',  label: 'Cédula de Extranjería'},
  { value: 'PAS', label: 'Pasaporte'            },
];

const HR = () => (
  <hr style={{ border: 'none', borderTop: '1px solid var(--gray-200)', margin: '24px 0' }} />
);

/**
 * Paso 2 — Clasificación e Información Básica del Sujeto Obligado / Contraparte.
 */
export default function PasoInfoBasica({ formData, onChange, onOpenHelp, errors }) {
  return (
    <div className="form-card">
      <h2 className="section-title">🏢 Clasificación e Información Básica</h2>
      <p className="section-subtitle">Datos generales de la empresa o persona natural</p>

      <div className="form-row">
        <FormField
          label="Tipo de Contraparte" name="tipo_contraparte" type="select" required
          value={formData.tipo_contraparte} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.tipo_contraparte}
          options={TIPOS_CONTRAPARTE}
        />
        <FormField
          label="Tipo de Persona" name="tipo_persona" type="select" required
          value={formData.tipo_persona} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.tipo_persona}
          options={TIPOS_PERSONA}
        />
        <FormField
          label="Tipo de Solicitud" name="tipo_solicitud" type="select" required
          value={formData.tipo_solicitud} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.tipo_solicitud}
          options={TIPOS_SOLICITUD}
        />
      </div>

      <HR />

      <div className="form-row single">
        <FormField
          label="Nombre o Razón Social" name="razon_social" required
          value={formData.razon_social} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.razon_social}
        />
      </div>

      <div className="form-row">
        <FormField
          label="Tipo de Identificación" name="tipo_identificacion" type="select" required
          value={formData.tipo_identificacion} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.tipo_identificacion}
          options={TIPOS_IDENTIFICACION}
        />
        <FormField
          label="Número de Identificación" name="numero_identificacion" required
          value={formData.numero_identificacion} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.numero_identificacion}
        />
      </div>

      <div className="form-row single">
        <FormField
          label="Dirección" name="direccion" required
          value={formData.direccion} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.direccion}
        />
      </div>

      <div className="form-row">
        <FormField
          label="País" name="pais"
          value={formData.pais || 'Colombia'} onChange={onChange}
          onOpenHelp={onOpenHelp}
        />
        <FormField
          label="Departamento" name="departamento" required
          value={formData.departamento} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.departamento}
        />
        <FormField
          label="Ciudad" name="ciudad" required
          value={formData.ciudad} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.ciudad}
        />
      </div>

      <div className="form-row">
        <FormField
          label="Teléfono" name="telefono" type="tel" required
          value={formData.telefono} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.telefono}
        />
        <FormField
          label="Fax" name="fax" type="tel"
          value={formData.fax} onChange={onChange}
          onOpenHelp={onOpenHelp}
        />
        <FormField
          label="Correo Electrónico" name="correo" type="email" required
          value={formData.correo} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.correo}
        />
      </div>

      <div className="form-row">
        <FormField
          label="Código Actividad ICA" name="codigo_ica"
          value={formData.codigo_ica} onChange={onChange}
          onOpenHelp={onOpenHelp}
        />
        <FormField
          label="Página Web" name="pagina_web" type="url"
          value={formData.pagina_web} onChange={onChange}
          onOpenHelp={onOpenHelp}
        />
      </div>
    </div>
  );
}
