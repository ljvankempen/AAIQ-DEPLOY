#!/usr/bin/env bash
# ==============================================================================
# TAPERC Public Gateway — VPS Deployment, Update & Recovery Tool
# Target directory: /opt/aaiq/taperc/public-taperc
# Runtime user: aaiq (group: aaiq)
# Public URL: https://taperc.aaiq.nl
# ==============================================================================

set -euo pipefail

# Configuration Constants
TARGET_BASE_DIR="/opt/aaiq/taperc"
TARGET_APP_DIR="/opt/aaiq/taperc/public-taperc"
BACKUP_DIR="/opt/aaiq/taperc/backups"
RUNTIME_USER="aaiq"
RUNTIME_GROUP="aaiq"
SYSTEMD_SERVICE_NAME="taperc-gateway.service"
SYSTEMD_UNIT_PATH="/etc/systemd/system/${SYSTEMD_SERVICE_NAME}"
CADDYFILE_PATH="/etc/caddy/Caddyfile"
LOCAL_HEALTH_URL="http://127.0.0.1:8080/health"
LOCAL_INFO_URL="http://127.0.0.1:8080/api/v1/info"
LOCAL_PWA_URL="http://127.0.0.1:8080/remote"
LOCAL_MANIFEST_URL="http://127.0.0.1:8080/manifest.json"
LOCAL_SW_URL="http://127.0.0.1:8080/sw.js"
PUBLIC_HEALTH_URL="https://taperc.aaiq.nl/health"
PUBLIC_INFO_URL="https://taperc.aaiq.nl/api/v1/info"
PUBLIC_PWA_URL="https://taperc.aaiq.nl/remote"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Determine script source directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" >&2
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root or with sudo."
        exit 1
    fi
}

ensure_runtime_user() {
    log_info "Verifying runtime user and group: ${RUNTIME_USER}..."
    if ! getent group "${RUNTIME_GROUP}" >/dev/null 2>&1; then
        groupadd -r "${RUNTIME_GROUP}"
        log_info "Created group ${RUNTIME_GROUP}."
    fi

    if ! id -u "${RUNTIME_USER}" >/dev/null 2>&1; then
        useradd -r -g "${RUNTIME_GROUP}" -s /bin/false -d "${TARGET_BASE_DIR}" "${RUNTIME_USER}"
        log_info "Created system user ${RUNTIME_USER}."
    else
        log_info "System user ${RUNTIME_USER} already exists."
    fi
}

ensure_directories() {
    log_info "Creating and verifying target directories..."
    mkdir -p "${TARGET_BASE_DIR}"
    mkdir -p "${TARGET_APP_DIR}/config"
    mkdir -p "${TARGET_APP_DIR}/src"
    mkdir -p "${TARGET_APP_DIR}/systemd"
    mkdir -p "${TARGET_APP_DIR}/caddy"
    mkdir -p "${TARGET_APP_DIR}/deploy"
    mkdir -p "${TARGET_APP_DIR}/static"
    mkdir -p "${TARGET_APP_DIR}/releases/firmware"
    mkdir -p "${TARGET_APP_DIR}/static/firmware"
    mkdir -p "${BACKUP_DIR}"
    mkdir -p /var/log/caddy

    chown -R "${RUNTIME_USER}:${RUNTIME_GROUP}" "${TARGET_BASE_DIR}"
    chmod 750 "${TARGET_BASE_DIR}" "${TARGET_APP_DIR}"
    chmod 700 "${BACKUP_DIR}"
}

create_backup() {
    local backup_timestamp
    backup_timestamp="$(date '+%Y%m%d_%H%M%S')"
    local backup_file="${BACKUP_DIR}/taperc-backup-${backup_timestamp}.tar.gz"

    log_info "Creating deployment backup at: ${backup_file}..."
    if [[ -d "${TARGET_APP_DIR}" ]]; then
        tar -czf "${backup_file}" \
            -C "${TARGET_BASE_DIR}" \
            --exclude="public-taperc/.venv" \
            --exclude="public-taperc/__pycache__" \
            --exclude="public-taperc/src/__pycache__" \
            --exclude="public-taperc/tests/__pycache__" \
            public-taperc 2>/dev/null || true

        chmod 600 "${backup_file}"
        chown root:root "${backup_file}"
        log_success "Backup successfully created: ${backup_file}"
        echo "${backup_file}"
    else
        log_warn "Target directory does not exist yet. Skipping pre-backup."
        echo ""
    fi
}

deploy_source_files() {
    log_info "Deploying application source files from ${SOURCE_ROOT}..."

    # Check if sources are nested under gateway/ (in AAIQ-DEPLOY structure)
    if [[ ! -d "${SOURCE_ROOT}/src" && -d "${SOURCE_ROOT}/gateway" ]]; then
        local latest_gw_dir
        latest_gw_dir="$(find "${SOURCE_ROOT}/gateway" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort -V | tail -n 1 || true)"
        if [[ -n "${latest_gw_dir}" && -d "${latest_gw_dir}/src" ]]; then
            log_info "Dynamically detected Gateway release directory: ${latest_gw_dir}"
            cp -r "${latest_gw_dir}/src/"* "${TARGET_APP_DIR}/src/"
        fi
    elif [[ -d "${SOURCE_ROOT}/src" ]]; then
        # Deploy direct python source code
        cp -r "${SOURCE_ROOT}/src/"* "${TARGET_APP_DIR}/src/"
    fi

    # Deploy systemd, caddy, deploy descriptors & docs
    if [[ -d "${SOURCE_ROOT}/systemd" ]]; then
        cp -r "${SOURCE_ROOT}/systemd/"* "${TARGET_APP_DIR}/systemd/"
    fi
    if [[ -d "${SOURCE_ROOT}/caddy" ]]; then
        cp -r "${SOURCE_ROOT}/caddy/"* "${TARGET_APP_DIR}/caddy/"
    fi
    if [[ -d "${SOURCE_ROOT}/deploy" ]]; then
        cp -r "${SOURCE_ROOT}/deploy/"* "${TARGET_APP_DIR}/deploy/"
        chmod +x "${TARGET_APP_DIR}/deploy/"*.sh 2>/dev/null || true
    fi

    # Deploy static assets (PWA) dynamically
    local pwa_src_dir=""
    if [[ -d "${SOURCE_ROOT}/pwa" ]]; then
        # Discover the latest release version under pwa/
        local latest_pwa_dir
        latest_pwa_dir="$(find "${SOURCE_ROOT}/pwa" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort -V | tail -n 1 || true)"
        if [[ -n "${latest_pwa_dir}" && -d "${latest_pwa_dir}" ]]; then
            pwa_src_dir="${latest_pwa_dir}"
            log_info "Dynamically detected PWA release directory: ${latest_pwa_dir}"
        fi
    fi

    if [[ -z "${pwa_src_dir}" && -d "${SOURCE_ROOT}/static" ]]; then
        pwa_src_dir="${SOURCE_ROOT}/static"
    fi

    if [[ -n "${pwa_src_dir}" && -d "${pwa_src_dir}" ]]; then
        log_info "Deploying PWA static assets from ${pwa_src_dir} to ${TARGET_APP_DIR}/static/..."
        mkdir -p "${TARGET_APP_DIR}/static"
        cp -r "${pwa_src_dir}/"* "${TARGET_APP_DIR}/static/"
        chown -R "${RUNTIME_USER}:${RUNTIME_GROUP}" "${TARGET_APP_DIR}/static" 2>/dev/null || true
    fi

    # Deploy firmware OTA releases dynamically
    if [[ -d "${SOURCE_ROOT}/releases" ]]; then
        log_info "Deploying firmware releases from ${SOURCE_ROOT}/releases to ${TARGET_APP_DIR}/releases/..."
        mkdir -p "${TARGET_APP_DIR}/releases"
        cp -r "${SOURCE_ROOT}/releases/"* "${TARGET_APP_DIR}/releases/"
        chown -R "${RUNTIME_USER}:${RUNTIME_GROUP}" "${TARGET_APP_DIR}/releases" 2>/dev/null || true
    fi

    # Deploy static firmware OTA assets if present
    if [[ -d "${SOURCE_ROOT}/static/firmware" ]]; then
        mkdir -p "${TARGET_APP_DIR}/static/firmware"
        cp -r "${SOURCE_ROOT}/static/firmware/"* "${TARGET_APP_DIR}/static/firmware/"
        chown -R "${RUNTIME_USER}:${RUNTIME_GROUP}" "${TARGET_APP_DIR}/static/firmware" 2>/dev/null || true
    fi

    [[ -f "${SOURCE_ROOT}/requirements.txt" ]] && cp "${SOURCE_ROOT}/requirements.txt" "${TARGET_APP_DIR}/"
    [[ -f "${SOURCE_ROOT}/README.md" ]] && cp "${SOURCE_ROOT}/README.md" "${TARGET_APP_DIR}/"
    [[ -f "${SOURCE_ROOT}/.env.example" ]] && cp "${SOURCE_ROOT}/.env.example" "${TARGET_APP_DIR}/"
    [[ -f "${SOURCE_ROOT}/config/config.example.json" ]] && cp "${SOURCE_ROOT}/config/config.example.json" "${TARGET_APP_DIR}/config/"
    [[ -f "${SOURCE_ROOT}/config/secrets.example.json" ]] && cp "${SOURCE_ROOT}/config/secrets.example.json" "${TARGET_APP_DIR}/config/"

    log_success "Source files deployed successfully."
}

preserve_or_init_configs() {
    log_info "Managing configuration and secrets (strictly preserving existing production files)..."

    # config.json preservation
    if [[ ! -f "${TARGET_APP_DIR}/config/config.json" ]]; then
        if [[ -f "${TARGET_APP_DIR}/config/config.example.json" ]]; then
            log_warn "No production config.json found. Initializing from config.example.json..."
            cp "${TARGET_APP_DIR}/config/config.example.json" "${TARGET_APP_DIR}/config/config.json"
        fi
    else
        log_info "Existing production config.json preserved."
    fi

    # secrets.json preservation
    if [[ ! -f "${TARGET_APP_DIR}/config/secrets.json" ]]; then
        if [[ -f "${TARGET_APP_DIR}/config/secrets.example.json" ]]; then
            log_warn "No production secrets.json found. Initializing template from secrets.example.json..."
            cp "${TARGET_APP_DIR}/config/secrets.example.json" "${TARGET_APP_DIR}/config/secrets.json"
            log_warn "CRITICAL: Remember to populate real cryptographic HMAC secrets in ${TARGET_APP_DIR}/config/secrets.json!"
        fi
    else
        log_info "Existing production secrets.json preserved."
    fi

    # .env preservation
    if [[ ! -f "${TARGET_APP_DIR}/.env" ]]; then
        if [[ -f "${TARGET_APP_DIR}/.env.example" ]]; then
            log_info "Initializing .env from .env.example..."
            cp "${TARGET_APP_DIR}/.env.example" "${TARGET_APP_DIR}/.env"
        fi
    else
        log_info "Existing .env preserved."
    fi

    # Set strict permissions on secrets and configs
    chown -R "${RUNTIME_USER}:${RUNTIME_GROUP}" "${TARGET_APP_DIR}"
    if [[ -f "${TARGET_APP_DIR}/config/secrets.json" ]]; then
        chmod 600 "${TARGET_APP_DIR}/config/secrets.json"
        chown "${RUNTIME_USER}:${RUNTIME_GROUP}" "${TARGET_APP_DIR}/config/secrets.json"
    fi
    if [[ -f "${TARGET_APP_DIR}/.env" ]]; then
        chmod 600 "${TARGET_APP_DIR}/.env"
        chown "${RUNTIME_USER}:${RUNTIME_GROUP}" "${TARGET_APP_DIR}/.env"
    fi
    if [[ -f "${TARGET_APP_DIR}/config/config.json" ]]; then
        chmod 640 "${TARGET_APP_DIR}/config/config.json"
        chown "${RUNTIME_USER}:${RUNTIME_GROUP}" "${TARGET_APP_DIR}/config/config.json"
    fi
}

setup_python_venv() {
    log_info "Setting up Python virtual environment at ${TARGET_APP_DIR}/.venv..."

    if [[ ! -d "${TARGET_APP_DIR}/.venv" ]]; then
        log_info "Creating new virtual environment as user ${RUNTIME_USER}..."
        (cd "${TARGET_APP_DIR}" && sudo -H -u "${RUNTIME_USER}" HOME="${TARGET_BASE_DIR}" python3 -m venv "${TARGET_APP_DIR}/.venv")
    fi

    log_info "Upgrading pip and installing dependencies..."
    (cd "${TARGET_APP_DIR}" && sudo -H -u "${RUNTIME_USER}" HOME="${TARGET_BASE_DIR}" "${TARGET_APP_DIR}/.venv/bin/pip" install --upgrade pip setuptools wheel --no-cache-dir --quiet)
    if [[ -f "${TARGET_APP_DIR}/requirements.txt" ]]; then
        (cd "${TARGET_APP_DIR}" && sudo -H -u "${RUNTIME_USER}" HOME="${TARGET_BASE_DIR}" "${TARGET_APP_DIR}/.venv/bin/pip" install -r "${TARGET_APP_DIR}/requirements.txt" --no-cache-dir --quiet)
        log_success "Dependencies installed successfully."
    fi
}

validate_production_runtime() {
    log_info "Validating production Python runtime and syntax under user ${RUNTIME_USER}..."
    
    if [[ ! -f "${TARGET_APP_DIR}/.venv/bin/python3" ]]; then
        log_error "Python binary not found at ${TARGET_APP_DIR}/.venv/bin/python3"
        return 1
    fi

    # 1. Byte-compile production sources to ensure syntax integrity
    if [[ -d "${TARGET_APP_DIR}/src" ]]; then
        log_info "Compiling Python source files in ${TARGET_APP_DIR}/src..."
        if ! (cd "${TARGET_APP_DIR}" && sudo -H -u "${RUNTIME_USER}" HOME="${TARGET_BASE_DIR}" "${TARGET_APP_DIR}/.venv/bin/python3" -m compileall -q "${TARGET_APP_DIR}/src"); then
            log_error "Python bytecode compilation failed in ${TARGET_APP_DIR}/src!"
            return 1
        fi
        log_success "Bytecode compilation check passed."
    fi

    # 2. Verify runtime dependencies and module imports in production context
    log_info "Verifying core TAPERC runtime imports under user ${RUNTIME_USER}..."
    if ! (cd "${TARGET_APP_DIR}" && sudo -H -u "${RUNTIME_USER}" HOME="${TARGET_BASE_DIR}" PYTHONPATH="${TARGET_APP_DIR}" "${TARGET_APP_DIR}/.venv/bin/python3" -c "import aiohttp, ssl, json, pathlib; from src import config, routes, server; print('✓ TAPERC runtime import verification successful')"); then
        log_error "TAPERC runtime module import verification failed under user ${RUNTIME_USER}!"
        return 1
    fi

    log_success "Production runtime validation passed successfully."
    return 0
}

run_tests() {
    log_info "Running development test suite inside virtual environment (if present)..."
    if [[ -d "${TARGET_APP_DIR}/tests" ]] && [[ -f "${TARGET_APP_DIR}/.venv/bin/pytest" ]]; then
        if (cd "${TARGET_APP_DIR}" && sudo -H -u "${RUNTIME_USER}" HOME="${TARGET_BASE_DIR}" PYTHONPATH="${TARGET_APP_DIR}" "${TARGET_APP_DIR}/.venv/bin/pytest" "${TARGET_APP_DIR}/tests" -o cache_dir=/tmp/.pytest_cache -q); then
            log_success "All tests passed successfully."
            return 0
        else
            log_error "Test suite failed!"
            return 1
        fi
    else
        log_info "Pytest or tests directory not present in production environment. Skipping test execution."
        return 0
    fi
}

install_systemd_service() {
    log_info "Configuring systemd service..."

    local service_source="${TARGET_APP_DIR}/systemd/${SYSTEMD_SERVICE_NAME}"
    if [[ -f "${service_source}" ]]; then
        cp "${service_source}" "${SYSTEMD_UNIT_PATH}"
        chmod 644 "${SYSTEMD_UNIT_PATH}"
        systemctl daemon-reload
        systemctl enable "${SYSTEMD_SERVICE_NAME}"
        log_success "Systemd service ${SYSTEMD_SERVICE_NAME} installed and enabled."
    else
        log_error "Systemd template not found at ${service_source}."
        exit 1
    fi
}

restart_service() {
    log_info "Restarting ${SYSTEMD_SERVICE_NAME}..."
    systemctl restart "${SYSTEMD_SERVICE_NAME}"
    sleep 2

    if systemctl is-active --quiet "${SYSTEMD_SERVICE_NAME}"; then
        log_success "Service ${SYSTEMD_SERVICE_NAME} is active and running."
    else
        log_error "Service ${SYSTEMD_SERVICE_NAME} failed to start!"
        systemctl status "${SYSTEMD_SERVICE_NAME}" --no-pager || true
        return 1
    fi
}

validate_caddy() {
    log_info "Validating Caddy reverse proxy configuration..."
    if command -v caddy >/dev/null 2>&1; then
        if [[ -f "${CADDYFILE_PATH}" ]]; then
            if caddy validate --config "${CADDYFILE_PATH}" 2>/dev/null; then
                log_success "Caddyfile is valid."
                
                # Check if taperc domain is present in Caddyfile
                if grep -q "taperc.aaiq.nl" "${CADDYFILE_PATH}"; then
                    log_info "taperc.aaiq.nl block is present in ${CADDYFILE_PATH}."
                    # Soft reload Caddy
                    if systemctl is-active --quiet caddy; then
                        log_info "Reloading Caddy..."
                        systemctl reload caddy || log_warn "Caddy reload returned non-zero, but service is running."
                    fi
                else
                    log_warn "Notice: 'taperc.aaiq.nl' block not detected in ${CADDYFILE_PATH}."
                    log_warn "Please ensure Caddy is configured using the snippet from ${TARGET_APP_DIR}/caddy/Caddyfile.example."
                fi
            else
                log_warn "Caddyfile validation failed! Please check ${CADDYFILE_PATH}."
            fi
        else
            log_warn "No Caddyfile found at ${CADDYFILE_PATH}."
        fi
    else
        log_warn "Caddy binary not found in PATH. Skipping Caddy validation."
    fi
}

check_local_health() {
    log_info "Checking local health endpoint (${LOCAL_HEALTH_URL} & ${LOCAL_INFO_URL})..."
    local retries=5
    local wait_sec=2

    for ((i=1; i<=retries; i++)); do
        if curl -s -f -m 5 "${LOCAL_HEALTH_URL}" >/dev/null 2>&1; then
            local info_json
            info_json="$(curl -s -f -m 5 "${LOCAL_INFO_URL}" 2>/dev/null || echo "")"
            log_success "Local health check PASSED (HTTP 200)."
            if [[ -n "${info_json}" ]]; then
                log_info "Local Gateway Info: ${info_json}"
            fi

            # Verify PWA local endpoints if static files were deployed
            if [[ -d "${TARGET_APP_DIR}/static" && -f "${TARGET_APP_DIR}/static/index.html" ]]; then
                if curl -s -f -m 5 "${LOCAL_PWA_URL}" >/dev/null 2>&1; then
                    log_success "Local PWA SPA route (${LOCAL_PWA_URL}) PASSED (HTTP 200)."
                else
                    log_warn "Local PWA SPA route (${LOCAL_PWA_URL}) did not return HTTP 200."
                fi
                if curl -s -f -m 5 "${LOCAL_MANIFEST_URL}" >/dev/null 2>&1; then
                    log_success "Local PWA manifest (${LOCAL_MANIFEST_URL}) PASSED (HTTP 200)."
                fi
                if curl -s -f -m 5 "${LOCAL_SW_URL}" >/dev/null 2>&1; then
                    log_success "Local PWA Service Worker (${LOCAL_SW_URL}) PASSED (HTTP 200)."
                fi
            fi

            # Verify OTA firmware release endpoint if firmware files were deployed
            if [[ -d "${TARGET_APP_DIR}/releases" || -d "${TARGET_APP_DIR}/static/firmware" ]]; then
                if curl -s -f -m 5 "http://127.0.0.1:8080/api/v1/ota/release" >/dev/null 2>&1; then
                    log_success "Local OTA firmware release endpoint (http://127.0.0.1:8080/api/v1/ota/release) PASSED (HTTP 200)."
                fi
            fi
            return 0
        fi
        log_warn "Local health check attempt ${i}/${retries} failed. Retrying in ${wait_sec}s..."
        sleep "${wait_sec}"
    done

    log_error "Local health check FAILED after ${retries} attempts."
    return 1
}

check_public_health() {
    log_info "Checking public HTTPS endpoint (${PUBLIC_HEALTH_URL} & ${PUBLIC_INFO_URL})..."
    if curl -s -f -m 8 "${PUBLIC_HEALTH_URL}" >/dev/null 2>&1; then
        local pub_info
        pub_info="$(curl -s -f -m 8 "${PUBLIC_INFO_URL}" 2>/dev/null || echo "")"
        log_success "Public HTTPS health check PASSED (https://taperc.aaiq.nl)."
        if [[ -n "${pub_info}" ]]; then
            log_info "Public Gateway Info: ${pub_info}"
        fi
        return 0
    else
        log_warn "Public HTTPS health check failed or domain not reachable from this node."
        log_warn "If this is a fresh setup or DNS/TLS is still provisioning, this may take a moment."
        return 0 # Non-fatal warning for local scripts
    fi
}

do_rollback() {
    local backup_archive="${1:-}"

    if [[ -z "${backup_archive}" ]]; then
        # Find latest backup
        backup_archive="$(ls -t "${BACKUP_DIR}"/*.tar.gz 2>/dev/null | head -n 1 || true)"
    fi

    if [[ -z "${backup_archive}" ]] || [[ ! -f "${backup_archive}" ]]; then
        log_error "No backup archive found to restore in ${BACKUP_DIR}."
        exit 1
    fi

    log_warn "Initiating recovery/rollback using backup: ${backup_archive}..."

    # Stop service if active
    if systemctl is-active --quiet "${SYSTEMD_SERVICE_NAME}"; then
        log_info "Stopping ${SYSTEMD_SERVICE_NAME} before restoration..."
        systemctl stop "${SYSTEMD_SERVICE_NAME}"
    fi

    # Extract backup over target directory
    log_info "Restoring files from ${backup_archive}..."
    tar -xzf "${backup_archive}" -C "${TARGET_BASE_DIR}"

    # Re-apply ownership & permissions
    chown -R "${RUNTIME_USER}:${RUNTIME_GROUP}" "${TARGET_BASE_DIR}"
    chmod 750 "${TARGET_BASE_DIR}" "${TARGET_APP_DIR}"
    if [[ -f "${TARGET_APP_DIR}/config/secrets.json" ]]; then
        chmod 600 "${TARGET_APP_DIR}/config/secrets.json"
    fi
    if [[ -f "${TARGET_APP_DIR}/.env" ]]; then
        chmod 600 "${TARGET_APP_DIR}/.env"
    fi

    # Reload systemd and start service
    systemctl daemon-reload
    restart_service
    check_local_health
    check_public_health

    log_success "Rollback and recovery completed successfully!"
}

cmd_install() {
    check_root
    cd "${TARGET_BASE_DIR}" || true
    log_info "Starting TAPERC Public Gateway initial installation..."

    ensure_runtime_user
    ensure_directories
    deploy_source_files
    preserve_or_init_configs
    setup_python_venv
    validate_production_runtime
    install_systemd_service
    restart_service
    validate_caddy
    check_local_health
    check_public_health

    log_success "================================================================"
    log_success "TAPERC Public Gateway installation completed successfully!"
    log_success "Installed under: ${TARGET_APP_DIR}"
    log_success "Runtime user:    ${RUNTIME_USER}:${RUNTIME_GROUP}"
    log_success "================================================================"
}

cmd_update() {
    check_root
    cd "${TARGET_BASE_DIR}" || true
    log_info "Starting TAPERC Public Gateway update procedure..."

    ensure_runtime_user
    ensure_directories

    # 1. Automatic pre-update backup
    local backup_file
    backup_file="$(create_backup)"

    # 2. Deploy source files (configs preserved)
    deploy_source_files
    preserve_or_init_configs

    # 3. Update virtualenv & dependencies
    setup_python_venv

    # 4. Validate production runtime
    if ! validate_production_runtime; then
        log_error "Production runtime validation failed after update! Initiating automatic rollback..."
        if [[ -n "${backup_file}" ]]; then
            do_rollback "${backup_file}"
        fi
        exit 1
    fi

    # 5. Update systemd service unit & restart
    install_systemd_service
    if ! restart_service; then
        log_error "Service failed to restart after update! Initiating automatic rollback..."
        if [[ -n "${backup_file}" ]]; then
            do_rollback "${backup_file}"
        fi
        exit 1
    fi

    # 6. Validate Caddy & perform health check
    validate_caddy
    if ! check_local_health; then
        log_error "Local health check failed after update! Initiating automatic rollback..."
        if [[ -n "${backup_file}" ]]; then
            do_rollback "${backup_file}"
        fi
        exit 1
    fi

    check_public_health

    log_success "================================================================"
    log_success "TAPERC Public Gateway update completed successfully!"
    log_success "Backup preserved at: ${backup_file}"
    log_success "================================================================"
}

cmd_backup() {
    check_root
    ensure_directories
    local backup_file
    backup_file="$(create_backup)"
    log_success "Standalone backup created: ${backup_file}"
}

cmd_rollback() {
    check_root
    local specific_backup="${2:-}"
    do_rollback "${specific_backup}"
}

cmd_health() {
    log_info "Checking TAPERC Gateway service and health status..."
    
    echo "--- Systemd Service ---"
    if systemctl is-active --quiet "${SYSTEMD_SERVICE_NAME}"; then
        echo -e "Status: ${GREEN}ACTIVE (running)${NC}"
    else
        echo -e "Status: ${RED}INACTIVE / FAILED${NC}"
    fi

    echo "--- Port Listener (8080) ---"
    if ss -ltnp 2>/dev/null | grep -q ":8080"; then
        echo -e "Port 8080: ${GREEN}LISTENING${NC}"
    else
        echo -e "Port 8080: ${RED}NOT LISTENING${NC}"
    fi

    echo "--- Local Health Endpoint ---"
    check_local_health || true

    echo "--- Public Health Endpoint ---"
    check_public_health || true

    echo "--- Caddy Status ---"
    validate_caddy || true
}

show_usage() {
    cat <<EOF
TAPERC Public Gateway — VPS Deployment & Recovery Tool

Usage:
  sudo ./deploy.sh <command> [options]

Commands:
  install       Perform initial idempotent installation of TAPERC Gateway under /opt/aaiq/taperc/public-taperc
  update        Perform safe update: creates backup, updates files, preserves configs/secrets, tests, restarts & verifies (with auto-rollback on failure)
  backup        Create a standalone timestamped backup in /opt/aaiq/taperc/backups/
  rollback      Restore from latest backup (or specify a path to a backup archive)
  health        Execute local and public health checks and report system status
  test          Run pytest test suite in the virtual environment
  help          Show this help message

Examples:
  sudo ./deploy.sh install
  sudo ./deploy.sh update
  sudo ./deploy.sh backup
  sudo ./deploy.sh rollback
  sudo ./deploy.sh rollback /opt/aaiq/taperc/backups/taperc-backup-20260912_120000.tar.gz
  sudo ./deploy.sh health
EOF
}

# Main Dispatcher
COMMAND="${1:-help}"

case "${COMMAND}" in
    install)
        cmd_install
        ;;
    update)
        cmd_update
        ;;
    backup)
        cmd_backup
        ;;
    rollback|restore)
        cmd_rollback "$@"
        ;;
    health|status|check)
        cmd_health
        ;;
    test)
        check_root
        run_tests
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        log_error "Unknown command: ${COMMAND}"
        show_usage
        exit 1
        ;;
esac
