# 🎯 Karmacadabra: Economía de Agentes sin Confianza

> Agentes de IA que compran/venden datos de forma autónoma usando micropagos sin gas basados en blockchain

**🇪🇸 Versión en Español** | **[🇺🇸 English Version](./README.md)**

> **⚡ Importante:** Esto implementa una **versión EXTENDIDA de ERC-8004** con reputación bidireccional (¡NO la especificación base!) desplegada en **Avalanche** - el hogar de **Ultravioleta DAO**. Tanto compradores como vendedores se califican mutuamente después de las transacciones.

[![Avalanche](https://img.shields.io/badge/Avalanche-Fuji-E84142?logo=avalanche)](https://testnet.snowtrace.io/)
[![ERC-8004](https://img.shields.io/badge/ERC--8004%20Extended-Bidirectional%20Rating-blue)](https://eips.ethereum.org/EIPS/eip-8004)
[![x402](https://img.shields.io/badge/x402-Payment%20Protocol-green)](https://www.x402.org)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/)
[![Rust](https://img.shields.io/badge/Rust-Latest-orange?logo=rust)](https://www.rust-lang.org/)

---

## 🎯 ¿Qué es Karmacadabra?

**Karmacadabra** es un ecosistema de agentes de IA autónomos que **compran y venden datos** sin intervención humana utilizando:

- **ERC-8004 Extendido** - **¡NO la implementación base!** Esta es una extensión personalizada que habilita **reputación bidireccional** (tanto compradores como vendedores se califican entre sí)
- **Protocolo A2A** (Pydantic AI) para comunicación entre agentes
- **x402 + EIP-3009** para micropagos HTTP (¡sin gas!)
- **CrewAI** para orquestación de múltiples agentes

### 🏔️ Desplegado en Avalanche - Nuestro Hogar

**Karmacadabra vive en Avalanche**, el hogar nativo de blockchain de **Ultravioleta DAO**. Elegimos Avalanche por:

- **Finalidad rápida**: Tiempos de bloque de 2 segundos para transacciones instantáneas de agentes
- **Costos bajos**: Tarifas de gas mínimas hacen que los micropagos sean económicamente viables
- **Compatibilidad EVM**: Soporte completo de Solidity con herramientas de Ethereum
- **Alineación con DAO**: Avalanche es donde Ultravioleta DAO nació y prospera

Actualmente en **testnet Fuji**, con despliegue en mainnet planificado después de auditorías.

### El Problema que Resolvemos

**Karma-Hello** tiene registros ricos de chat de Twitch pero sin contexto de audio.
**Abracadabra** tiene transcripciones de streams pero sin datos de chat.

**Solución**: Los agentes negocian y compran de forma autónoma datos complementarios, construyendo un contexto completo de streaming. Todas las transacciones son verificadas, on-chain, y sin gas.

---

## 🚀 Inicio Rápido (30 minutos)

```bash
# 1. Clonar repositorio
git clone https://github.com/ultravioletadao/karmacadabra.git
cd karmacadabra

# 2. Obtener AVAX de testnet
# Visitar: https://faucet.avax.network/

# 3. Desplegar contratos
cd erc-20 && ./deploy-fuji.sh && cd ..
cd erc-8004 && ./deploy-fuji.sh && cd ..

# 4. Iniciar facilitador
cd x402-rs && cargo run &

# 5. Ejecutar demo
python demo.py
```

**Guía completa**: Ver [QUICKSTART.md](./QUICKSTART.md)

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│   AVALANCHE FUJI TESTNET (Nuestro Hogar - Capa 1)      │
│  ┌──────────────────┐    ┌──────────────────────┐      │
│  │  Token UVD V2    │    │ ERC-8004 EXTENDIDO   │      │
│  │  (EIP-3009)      │    │  (¡Bidireccional!)   │      │
│  │  Txs sin gas ✓   │    │  • Identidad         │      │
│  └──────────────────┘    │  • Reputación        │      │
│                          │  • Validación        │      │
│                          └──────────────────────┘      │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │
┌─────────────────────────┴─────────────────────────────┐
│   Facilitador x402 (Capa 2) - Rust                    │
│   • Verifica firmas EIP-712                           │
│   • Ejecuta transferWithAuthorization()               │
│   • Sin estado, no requiere base de datos             │
└─────────────────────────────────────────────────────────┘
            ▲                            ▲
            │                            │
┌───────────┴────────┐      ┌───────────┴────────┐
│ Agente Karma-Hello │      │ Agente Abracadabra │
│ • Vende: Logs chat │      │ • Vende: Transcripc│
│ • Compra: Transcr. │      │ • Compra: Logs chat│
│ • Precio: 0.01 UVD │      │ • Precio: 0.02 UVD │
│ • Datos: MongoDB   │      │ • Datos: SQLite    │
└────────────────────┘      └─────────────────────┘
            ▲                            ▲
            └────────┬───────────────────┘
                     ▼
         ┌────────────────────┐
         │  Agente Validador  │
         │  • Crew de CrewAI  │
         │  • Puntaje calidad │
         │  • Tarifa: 0.001   │
         └────────────────────┘
```

---

## 💰 ¿Qué se Puede Monetizar?

### Servicios de Karma-Hello (20+ productos)
- **Nivel 1** (0.01 UVD): Logs de chat, actividad de usuarios
- **Nivel 2** (0.10 UVD): Predicciones ML, análisis de sentimiento
- **Nivel 3** (0.20 UVD): Detección de fraude, salud económica
- **Empresarial** (hasta 200 UVD): Marca blanca, modelos personalizados

### Servicios de Abracadabra (30+ productos)
- **Nivel 1** (0.02 UVD): Transcripciones crudas, mejoradas
- **Nivel 2** (0.15 UVD): Generación de clips, posts de blog
- **Nivel 3** (0.35 UVD): Motor predictivo, recomendaciones
- **Nivel 4** (1.50 UVD): Edición automática de video, generación de imágenes
- **Empresarial** (hasta 100 UVD): Modelos de IA personalizados

**Catálogo completo**: [MONETIZATION_OPPORTUNITIES.md](./MONETIZATION_OPPORTUNITIES.md)

---

## 📂 Estructura del Repositorio

```
karmacadabra/
├── erc-20/                    # Token UVD V2 (EIP-3009)
├── erc-8004/                  # ERC-8004 Extendido - Registros de reputación bidireccional
├── x402-rs/                   # Facilitador de pagos (Rust)
├── validator/                 # Agente validador (Python + CrewAI)
├── karma-hello-agent/         # Agentes vendedor/comprador de logs de chat
├── abracadabra-agent/         # Agentes vendedor/comprador de transcripciones
├── MASTER_PLAN.md            # Visión completa y hoja de ruta
├── ARCHITECTURE.md           # Arquitectura técnica
├── MONETIZATION_OPPORTUNITIES.md
├── QUICKSTART.md             # Guía de configuración de 30 min
├── CLAUDE.md                 # Guía para Claude Code
└── INDEX.md                  # Índice de documentación
```

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología | Propósito |
|-------|-----------|---------|
| **Blockchain** | Avalanche Fuji | Testnet EVM para contratos inteligentes |
| **Contratos** | Solidity + Foundry | Registros ERC-8004 + token UVD |
| **Facilitador** | Rust (Axum) | Verificación de pagos x402 |
| **Agentes** | Python 3.11+ | Runtime de agentes de IA |
| **Framework IA** | CrewAI | Orquestación multi-agente |
| **LLM** | GPT-4o | Análisis y validación |
| **Web3** | web3.py + ethers-rs | Interacción con blockchain |
| **Datos** | MongoDB + SQLite + Cognee | Fuentes de datos de agentes |

---

## 🎯 Características Clave

✅ **Micropagos sin Gas**: Los agentes no necesitan ETH/AVAX para gas
✅ **Reputación Bidireccional**: Extensión personalizada de ERC-8004 - compradores Y vendedores se califican entre sí (¡no está en la especificación base!)
✅ **Nativo de Avalanche**: Desplegado en nuestra cadena de origen para rendimiento óptimo
✅ **Validación sin Confianza**: Validadores independientes verifican la calidad de los datos
✅ **Descubrimiento de Agentes**: AgentCards del protocolo A2A en `/.well-known/agent-card`
✅ **Flujos Multi-Agente**: Crews de CrewAI para tareas complejas
✅ **50+ Servicios Monetizables**: Desde $0.01 hasta $200 UVD por servicio

---

## 📚 Documentación

| Documento | Descripción | Tiempo |
|----------|-------------|------|
| [QUICKSTART.md](./QUICKSTART.md) | Funcionando en 30 minutos | 30 min |
| [MASTER_PLAN.md](./MASTER_PLAN.md) | Visión completa y hoja de ruta | 60 min |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Profundización técnica | 45 min |
| [MONETIZATION_OPPORTUNITIES.md](./MONETIZATION_OPPORTUNITIES.md) | Todos los servicios y precios | 30 min |
| [CLAUDE.md](./CLAUDE.md) | Guía para desarrolladores | 15 min |
| [INDEX.md](./INDEX.md) | Índice de documentación | 5 min |

**READMEs de Componentes**: Cada carpeta tiene instrucciones detalladas de configuración.

---

## 🧪 Estado del Desarrollo

| Fase | Componente | Estado |
|-------|-----------|--------|
| **Fase 1** | Token UVD V2 | 🔴 Listo para desplegar |
| **Fase 1** | Registros ERC-8004 Extendidos | 🔴 Listo para desplegar |
| **Fase 1** | Facilitador x402 | 🔴 Listo para construir |
| **Fase 2** | Agente Validador | 🔴 Por implementar |
| **Fase 3** | Agentes Karma-Hello | 🔴 Por implementar |
| **Fase 4** | Agentes Abracadabra | 🔴 Por implementar |
| **Fase 5** | Pruebas de Extremo a Extremo | 🔴 Pendiente |

**Cronograma**: 6 semanas hasta demo lista para producción

---

## 🔧 Requisitos

- **Python** 3.11+
- **Rust** última versión estable
- **Foundry** (forge, anvil, cast)
- **Node.js** 18+ (opcional, para frontend)
- **AVAX** en testnet Fuji (gratis desde faucet)
- **Clave API de OpenAI** (para agentes CrewAI)

---

## 🚦 Comenzando

### 1. Prerequisitos
```bash
# Instalar Foundry
curl -L https://foundry.paradigm.xyz | bash
foundryup

# Instalar Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Python 3.11+
python --version  # Debe ser 3.11 o superior
```

### 2. Obtener AVAX de Testnet
Visita https://faucet.avax.network/ y solicita AVAX para tu wallet.

### 3. Desplegar Infraestructura
```bash
cd erc-20
cp .env.example .env
# Editar .env con tu PRIVATE_KEY
./deploy-fuji.sh

cd ../erc-8004
./deploy-fuji.sh

cd ../x402-rs
cargo build --release
cargo run
```

### 4. Ejecutar Demo
```bash
python demo.py
```

Ver [QUICKSTART.md](./QUICKSTART.md) para instrucciones detalladas.

---

## 🤝 Contribuir

1. Leer [MASTER_PLAN.md](./MASTER_PLAN.md) para entender la visión
2. Revisar la hoja de ruta para tareas disponibles
3. Implementar siguiendo la arquitectura en [ARCHITECTURE.md](./ARCHITECTURE.md)
4. Escribir pruebas para todo el código nuevo
5. Enviar PR con documentación

---

## 📖 Aprender Más

- **Especificación Base ERC-8004**: https://eips.ethereum.org/EIPS/eip-8004 (¡nosotros extendemos esto con calificaciones bidireccionales!)
- **Protocolo A2A**: https://ai.pydantic.dev/a2a/
- **Protocolo x402**: https://www.x402.org
- **EIP-3009**: https://eips.ethereum.org/EIPS/eip-3009
- **CrewAI**: https://docs.crewai.com/
- **Documentación Avalanche**: https://docs.avax.network/ (¡nuestra cadena de origen!)

### Curso de Agentes sin Confianza
https://intensivecolearn.ing/en/programs/trustless-agents

---

## ⚠️ Descargo de Responsabilidad

**SOLO TESTNET**: Este proyecto está actualmente desplegado en testnet Fuji de Avalanche. No usar con fondos reales. Los contratos inteligentes no han sido auditados.

Para despliegue en mainnet:
- [ ] Auditoría de contratos inteligentes por firma reputada
- [ ] Programa de bug bounty
- [ ] Timelock para funciones de administración
- [ ] Multi-sig para propiedad de contratos

---

## 📄 Licencia

Licencia MIT - Ver [LICENSE](./LICENSE)

---

## 🌟 Agradecimientos

- **Curso Trustless Agents** por Intensive CoLearning
- **Especificación Base ERC-8004** (que extendimos para reputación bidireccional)
- **x402-rs** implementación del protocolo
- **Pydantic AI** protocolo A2A
- **Avalanche** - nuestra blockchain de origen y la fundación de Ultravioleta DAO

---

## 💬 Contacto

- **Proyecto**: Ultravioleta DAO
- **Repositorio**: https://github.com/ultravioletadao/karmacadabra
- **Documentación**: Comenzar con [QUICKSTART.md](./QUICKSTART.md)

---

**Construido con ❤️ por Ultravioleta DAO**

*Empoderando agentes de IA autónomos para crear una economía de datos sin confianza*
