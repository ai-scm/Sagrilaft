import { RemovalPolicy } from 'aws-cdk-lib';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface EcrProps {
  readonly ambiente: string;
}

/**
 * ECR: Elastic Container Registry.
 *
 * Repositorios de Docker privados por servicio ECS.
 * Incluye política de ciclo de vida para retener solo las últimas 30 imágenes.
 */
export class Ecr extends Construct {
  public readonly backendRepo: ecr.Repository;
  public readonly frontendRepo: ecr.Repository;
  public readonly formularioPublicoRepo: ecr.Repository;
  public readonly portalInternoRepo: ecr.Repository;
  public readonly keycloakRepo: ecr.Repository;

  constructor(scope: Construct, id: string, props: EcrProps) {
    super(scope, id);

    this.backendRepo = this.buildRepository('BackendRepo', `sagrilaft-${props.ambiente}-backend`, props.ambiente);
    this.formularioPublicoRepo = this.buildRepository(
      'FormularioPublicoRepo',
      `sagrilaft-${props.ambiente}-formulario-publico`,
      props.ambiente,
    );
    this.portalInternoRepo = this.buildRepository(
      'PortalInternoRepo',
      `sagrilaft-${props.ambiente}-portal-interno`,
      props.ambiente,
    );
    this.keycloakRepo = this.buildRepository('KeycloakRepo', `sagrilaft-${props.ambiente}-keycloak`, props.ambiente);

    // Alias de compatibilidad con flujos existentes que aun esperan "frontendRepo".
    this.frontendRepo = this.formularioPublicoRepo;
  }

  private buildRepository(id: string, repositoryName: string, ambiente: string): ecr.Repository {
    return new ecr.Repository(this, id, {
      repositoryName,
      removalPolicy: ambiente === 'prod' ? RemovalPolicy.RETAIN : RemovalPolicy.DESTROY,
      emptyOnDelete: ambiente !== 'prod',
      imageScanOnPush: true,
      lifecycleRules: [
        {
          rulePriority: 1,
          description: 'Mantener las últimas 30 imágenes para ahorrar costos',
          maxImageCount: 30,
        },
      ],
    });
  }

  /**
   * Otorga permisos de solo lectura (pull) a un rol sobre ambos repositorios.
   * Útil para que ECS pueda descargar las imágenes.
   */
  public grantPull(grantee: iam.IGrantable): void {
    this.backendRepo.grantPull(grantee);
    this.formularioPublicoRepo.grantPull(grantee);
    this.portalInternoRepo.grantPull(grantee);
    this.keycloakRepo.grantPull(grantee);
  }
}
