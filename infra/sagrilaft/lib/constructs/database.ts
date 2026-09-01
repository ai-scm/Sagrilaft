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

    const rdsComputeClass = ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO);

    this.instance = new rds.DatabaseInstance(this, 'Postgres', {
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
      multiAz: false, // Free Tier no soporta Multi-AZ sin costos
      storageEncrypted: true,
      deletionProtection: true,
      backupRetention: Duration.days(7), // Acorde a la arquitectura de producción
      removalPolicy: RemovalPolicy.RETAIN,
    });
  }
}
