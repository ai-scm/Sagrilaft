import { Duration, RemovalPolicy } from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

export interface StorageProps {
  readonly ambiente: string;
  readonly dominioPortal: string;
}

/**
 * Storage: Bucket S3 con estructura de carpetas por empresa.
 *
 * Estructura:
 *   s3://bucket/<nit>/adjuntos/     ← docs subidos al formulario
 *   s3://bucket/<nit>/formularios/  ← PDF del formulario radicado
 *   s3://bucket/<nit>/manuales/     ← cargas manuales del portal
 *   s3://bucket/<nit>/reportes/     ← reportes finales
 *   s3://bucket/tmp/                ← archivos temporales (expiran 1 día)
 *
 * El backend genera presigned URLs para descargas desde el portal interno.
 */
export class Storage extends Construct {
  public readonly bucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: StorageProps) {
    super(scope, id);

    this.bucket = new s3.Bucket(this, 'Uploads', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: props.ambiente === 'prod',
      removalPolicy: RemovalPolicy.RETAIN,
      cors: [
        {
          allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.HEAD],
          allowedOrigins: [
            `https://${props.dominioPortal}`, // Dominio inyectado por ambiente
            'http://localhost:3000',          // Desarrollo local de React
            'http://localhost:5173'           // Desarrollo local de Vite
          ],
          allowedHeaders: ['*'],
          exposedHeaders: [
            'Content-Disposition',
            'Content-Type',
            'Content-Length',
            'ETag'
          ],
          maxAge: 3000,
        }
      ],
      lifecycleRules: [
        {
          id: 'expire-tmp',
          prefix: 'tmp/',
          expiration: Duration.days(1),
        },
      ],
    });
  }
}
