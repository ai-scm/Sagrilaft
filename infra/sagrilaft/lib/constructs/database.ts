import { Duration, RemovalPolicy } from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

import { SAGRILAFT_DB_NAME } from '../deployment-constants';

export interface DatabaseProps {
  readonly vpc: ec2.Vpc;
  readonly securityGroup: ec2.SecurityGroup;
  readonly credentialsSecret: secretsmanager.Secret;
  readonly ambiente: string;
  readonly subnetType: ec2.SubnetType;
}

/**
 * Database: Instancia RDS PostgreSQL 16 en subnet privada.
 * Usa VPC, subnets y SG de la red compartida para alojar RDS.
 *
 * Configurada con encriptación, protección contra eliminación,
 * y backups automáticos de 7 días.
 */
export class Database extends Construct {
  public readonly instance: rds.DatabaseInstance;

  constructor(scope: Construct, id: string, props: DatabaseProps) {
    super(scope, id);

    // Medido del 3 al 16 de noviembre de 2026: CPU promedio 4%, ~0,9 GB de memoria
    // usados y 11 conexiones como máximo en ambos ambientes. 2 GB sobran.
    // Producción: db.t3.small (x86). Staging/dev: db.t4g.small (Graviton, más barata).
    // Cambiarla en una instancia existente la reinicia (minutos sin base de datos).
    const rdsComputeClass = props.ambiente === 'prod'
      ? ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.SMALL)
      : ec2.InstanceType.of(ec2.InstanceClass.T4G, ec2.InstanceSize.SMALL);

    // Disco: producción conserva 100 GB. Fuera de producción, 20 GB gp3 (el mínimo de
    // RDS), con crecimiento automático hasta 50 GB; los datos ocupan menos de 1 GB.
    // RDS no permite achicar un disco, así que fuera de producción la instancia lleva
    // otro id: CloudFormation crea una base nueva y vacía, y la anterior queda fuera de
    // la pila (RETAIN) hasta borrarla a mano. Producción conserva su id y su base.
    const esProd = props.ambiente === 'prod';
    const disco: Partial<rds.DatabaseInstanceProps> = esProd
      ? {}
      : { allocatedStorage: 20, maxAllocatedStorage: 50, storageType: rds.StorageType.GP3 };

    this.instance = new rds.DatabaseInstance(this, esProd ? 'Postgres' : 'PostgresDisco20', {
      ...disco,
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_16,
      }),
      instanceType: rdsComputeClass,
      vpc: props.vpc,
      vpcSubnets: {
        subnetType: props.subnetType,
      },
      securityGroups: [props.securityGroup],
      databaseName: SAGRILAFT_DB_NAME,
      credentials: rds.Credentials.fromSecret(props.credentialsSecret),
      multiAz: false, // Diseño de producción elegido; recuperación Multi-AZ no está habilitada.
      storageEncrypted: true,
      deletionProtection: true,
      backupRetention: Duration.days(7), // Acorde a la arquitectura de producción
      removalPolicy: RemovalPolicy.RETAIN,
    });
  }
}
