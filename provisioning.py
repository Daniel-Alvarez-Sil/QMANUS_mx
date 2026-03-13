import asyncio
import os
import sys
import time

from dotenv import load_dotenv

from db import pool_manager

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# Cluster prefix: explicit env var takes priority, otherwise derived from TIDB_ADMIN_USER/TIDB_USER
CLUSTER_PREFIX = (
    os.getenv("TIDB_CLUSTER_PREFIX")
    or os.getenv("TIDB_USER", "").split(".")[0]
    or os.getenv("TIDB_ADMIN_USER", "").split(".")[0]
)


async def create_database(tenant_name: str) -> None:
    """Create the tenant database schema."""
    db_name = f"tenant_{tenant_name}"
    await pool_manager.execute_write(
        tenant_name,
        f"CREATE DATABASE IF NOT EXISTS `{db_name}`",
    )
    print(f"✓ Base de datos creada: {db_name}")


async def create_tables(tenant_name: str) -> None:
    """Create all tenant tables using fully-qualified names (no schema switch needed)."""
    db = f"tenant_{tenant_name}"

    tables = [
        f"""
        CREATE TABLE IF NOT EXISTS `{db}`.games (
            id          BIGINT PRIMARY KEY AUTO_RANDOM(5),
            name        VARCHAR(255) NOT NULL,
            description TEXT,
            price       DECIMAL(10, 2),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{db}`.customers (
            id         BIGINT PRIMARY KEY AUTO_RANDOM(5),
            name       VARCHAR(255) NOT NULL,
            email      VARCHAR(255) UNIQUE NOT NULL,
            phone      VARCHAR(20),
            country    VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{db}`.orders (
            id           BIGINT PRIMARY KEY AUTO_RANDOM(5),
            customer_id  BIGINT NOT NULL,
            order_date   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_amount DECIMAL(12, 2),
            status       VARCHAR(50) DEFAULT 'pending',
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            KEY idx_customer_id (customer_id),
            KEY idx_order_date  (order_date)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{db}`.order_items (
            id         BIGINT PRIMARY KEY AUTO_RANDOM(5),
            order_id   BIGINT NOT NULL,
            game_id    BIGINT NOT NULL,
            quantity   INT DEFAULT 1,
            unit_price DECIMAL(10, 2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            KEY idx_order_id (order_id),
            KEY idx_game_id  (game_id)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{db}`.recommendations (
            id          BIGINT PRIMARY KEY AUTO_RANDOM(5),
            customer_id BIGINT NOT NULL,
            game_id     BIGINT NOT NULL,
            score       DECIMAL(5, 2),
            reason      VARCHAR(255),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            KEY idx_customer_id (customer_id),
            KEY idx_game_id     (game_id)
        )
        """,
    ]

    for sql in tables:
        await pool_manager.execute_write(tenant_name, sql)

    print(f"✓ Tablas creadas para {tenant_name}: games, customers, orders, order_items, recommendations")


async def create_tenant_user(tenant_name: str) -> tuple[str, str]:
    """Create a per-tenant MySQL user with limited privileges."""
    tenant_user = f"{CLUSTER_PREFIX}.{tenant_name}_user"
    tenant_password = os.urandom(16).hex()
    db_name = f"tenant_{tenant_name}"

    await pool_manager.execute_write(
        tenant_name,
        f"CREATE USER IF NOT EXISTS '{tenant_user}'@'%' IDENTIFIED BY '{tenant_password}'",
    )
    await pool_manager.execute_write(
        tenant_name,
        f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{tenant_user}'@'%'",
    )
    await pool_manager.execute_write(tenant_name, "FLUSH PRIVILEGES")

    print(f"✓ Usuario creado: {tenant_user}")
    print(f"  Contraseña: {tenant_password}")
    print(f"  Permisos: Acceso total a {db_name}")

    return tenant_user, tenant_password


async def provision_tenant(tenant_name: str) -> dict:
    """Orchestrate the full tenant provisioning flow."""
    start_time = time.time()

    print(f"\n{'='*60}")
    print(f"Iniciando provisioning para tenant: {tenant_name}")
    print(f"{'='*60}\n")

    try:
        await create_database(tenant_name)
        await create_tables(tenant_name)
        tenant_user, tenant_password = await create_tenant_user(tenant_name)

        elapsed_time = time.time() - start_time

        print(f"\n{'='*60}")
        print(f"✓ Provisioning completado en {elapsed_time:.2f} segundos")
        print(f"{'='*60}\n")

        return {
            "status": "success",
            "tenant_name": tenant_name,
            "database": f"tenant_{tenant_name}",
            "user": tenant_user,
            "password": tenant_password,
            "time_seconds": elapsed_time,
        }
    except Exception as e:
        print(f"\n✗ Error durante provisioning: {e}")
        return {
            "status": "error",
            "tenant_name": tenant_name,
            "error": str(e),
        }
    finally:
        await pool_manager.close_all()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python provisioning.py <tenant_name>")
        print("Ejemplo: python provisioning.py acme_corp")
        sys.exit(1)

    result = asyncio.run(provision_tenant(sys.argv[1]))

    if result["status"] == "error":
        sys.exit(1)
