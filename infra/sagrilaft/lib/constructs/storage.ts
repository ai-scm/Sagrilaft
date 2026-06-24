import { Duration, RemovalPolicy } from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

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

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.bucket = new s3.Bucket(this, 'Uploads', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: false,
      removalPolicy: RemovalPolicy.RETAIN,
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
