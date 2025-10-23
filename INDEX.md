# 📚 Documentation Index

> Índice completo de documentación del ecosistema Trustless Agents

---

## 🎯 Comenzar Aquí

| Documento | Descripción | Tiempo |
|-----------|-------------|--------|
| **[QUICKSTART.md](./QUICKSTART.md)** | Setup rápido en 30 minutos | 30 min |
| **[MASTER_PLAN.md](./MASTER_PLAN.md)** | Plan maestro completo | 60 min |
| **[ARCHITECTURE.md](./ARCHITECTURE.md)** | Arquitectura técnica detallada | 45 min |
| **[VALIDATOR_BLOCKCHAIN_INTERACTION.md](./VALIDATOR_BLOCKCHAIN_INTERACTION.md)** | 🔴 **Aclaración**: Validator SÍ escribe on-chain | 15 min |

---

## 📦 Por Componente

### 🪙 GLUE Token (ERC-20)
```
erc-20/
├── README.md         → Guía completa del token
├── .env.example      → Template de configuración
└── contracts/        → Smart contracts
```

**Características**: ERC-20 + EIP-3009 (gasless) + EIP-2612 (permit)

---

### 🔐 ERC-8004 Registries
```
erc-8004/
├── README.md         → Guía de despliegue
├── DEPLOY-FUJI.md    → Instrucciones paso a paso
├── .env.fuji.example → Template de configuración
└── contracts/        → Smart contracts
    ├── IdentityRegistry.sol
    ├── ReputationRegistry.sol
    └── ValidationRegistry.sol
```

**Contratos**: Identity, Reputation, Validation

---

### 🎮 Karma-Hello Agent System
```
karma-hello-agent/
├── README.md         → Documentación completa
├── .env.example      → Template de configuración
└── agents/
    ├── karma_hello_seller.py   → Vende logs
    └── karma_hello_buyer.py    → Compra transcripts
```

**Vende**: Logs de streams de Twitch
**Compra**: Transcripciones de Abracadabra
**Precio**: 0.01 UVD por query

---

### 🎬 Abracadabra Agent System
```
abracadabra-agent/
├── README.md         → Documentación completa
├── .env.example      → Template de configuración
└── agents/
    ├── abracadabra_seller.py   → Vende transcripts
    └── abracadabra_buyer.py    → Compra logs
```

**Vende**: Transcripciones + Topics + Entities
**Compra**: Logs de Karma-Hello
**Precio**: 0.02 UVD por transcript

---

### 🔍 Validator Agent
```
validator/
├── README.md         → Documentación completa
├── .env.example      → Template de configuración
└── agents/
    └── validator_agent.py      → Validador independiente
```

**Función**: Valida calidad de datos antes de transacciones
**Fee**: 0.001 UVD por validación
**Basado en**: Bob del ejemplo ERC-8004

---

### 💸 x402 Facilitator
```
x402-rs/
├── CLAUDE.md         → Guía para desarrollo
├── crates/
│   ├── x402-axum/    → Server middleware
│   └── x402-reqwest/ → Client middleware
└── src/
    └── main.rs       → Facilitator binary
```

**URL**: https://facilitator.ultravioletadao.xyz
**Función**: Verificación y settlement de pagos x402

---

## 🎓 Guías de Aprendizaje

### Para Principiantes

1. **[QUICKSTART.md](./QUICKSTART.md)** - Setup en 30 minutos
2. **[erc-20/README.md](./erc-20/README.md)** - Entender UVD Token
3. **[erc-8004/README.md](./erc-8004/README.md)** - Entender ERC-8004

### Para Desarrolladores

1. **[MASTER_PLAN.md](./MASTER_PLAN.md)** - Visión completa
2. **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Decisiones técnicas
3. **[karma-hello-agent/README.md](./karma-hello-agent/README.md)** - Implementar agentes
4. **[x402-rs/CLAUDE.md](./x402-rs/CLAUDE.md)** - Protocolo x402

### Para Arquitectos

1. **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Arquitectura completa
2. **[MASTER_PLAN.md](./MASTER_PLAN.md)** - Decisiones de diseño
3. Código fuente de cada componente

---

## 🔗 Recursos Externos

### Protocolos y Estándares

- **ERC-8004**: https://eips.ethereum.org/EIPS/eip-8004
- **A2A Protocol**: https://ai.pydantic.dev/a2a/
- **x402 Protocol**: https://www.x402.org
- **EIP-3009**: https://eips.ethereum.org/EIPS/eip-3009
- **EIP-712**: https://eips.ethereum.org/EIPS/eip-712

### Herramientas

- **Foundry**: https://book.getfoundry.sh/
- **CrewAI**: https://docs.crewai.com/
- **Pydantic AI**: https://ai.pydantic.dev/
- **Cognee**: https://docs.cognee.ai/

### Avalanche

- **Docs**: https://docs.avax.network/
- **Faucet**: https://faucet.avax.network/
- **Explorer**: https://testnet.snowtrace.io/

### Curso

- **Trustless Agents**: https://intensivecolearn.ing/en/programs/trustless-agents

---

## 📊 Diagramas

### Flujo de Pago Completo
Ver: [ARCHITECTURE.md#flujos-de-datos](./ARCHITECTURE.md#-flujos-de-datos)

### Stack Tecnológico
Ver: [ARCHITECTURE.md#stack-tecnológico](./ARCHITECTURE.md#-stack-tecnológico)

### Arquitectura de Agentes
Ver: [MASTER_PLAN.md#arquitectura-del-sistema](./MASTER_PLAN.md#-arquitectura-del-sistema)

---

## 🛠️ Scripts Útiles

### Deploy Completo

```bash
# 1. Deploy UVD Token
cd erc-20 && ./deploy-fuji.sh && cd ..

# 2. Deploy ERC-8004
cd erc-8004 && ./deploy-fuji.sh && cd ..

# 3. Start facilitator
cd x402-rs && cargo run &

# 4. Register agents
cd validator && python scripts/register_validator.py
cd ../karma-hello-agent && python scripts/register_seller.py
cd ../abracadabra-agent && python scripts/register_seller.py

# 5. Run demo
python demo.py
```

### Testing

```bash
# Unit tests
cd karma-hello-agent && pytest tests/
cd ../abracadabra-agent && pytest tests/
cd ../validator && pytest tests/

# Integration test
python demo.py --network local
```

### Monitoring

```bash
# Ver logs de agentes
tail -f karma-hello-agent/logs/app.log
tail -f abracadabra-agent/logs/app.log
tail -f validator/logs/app.log

# Ver transacciones en Snowtrace
open https://testnet.snowtrace.io/address/0xYOUR_UVD_TOKEN
```

---

## 🎯 Roadmap de Lectura

### Semana 1: Fundamentos
- [ ] QUICKSTART.md
- [ ] erc-20/README.md
- [ ] erc-8004/README.md
- [ ] Deploy en Fuji

### Semana 2: Agentes
- [ ] karma-hello-agent/README.md
- [ ] abracadabra-agent/README.md
- [ ] validator/README.md
- [ ] Implementar agentes básicos

### Semana 3: Protocolos
- [ ] ARCHITECTURE.md
- [ ] x402-rs/CLAUDE.md
- [ ] Implementar A2A
- [ ] Integrar x402

### Semana 4: Producción
- [ ] MASTER_PLAN.md (completo)
- [ ] Testing exhaustivo
- [ ] Optimización
- [ ] Deploy completo

---

## 💡 Tips

### Debugging

1. **Contratos no despliegan**: Verificar balance AVAX en wallet
2. **Agentes no se registran**: Verificar addresses de contratos en .env
3. **Pagos fallan**: Verificar facilitator está corriendo
4. **CrewAI errores**: Verificar OPENAI_API_KEY en .env

### Performance

1. **Latencia alta**: Usar RPC local (Anvil) para testing
2. **Gas alto**: Optimizar batch de transacciones
3. **DB slow**: Agregar índices en MongoDB/SQLite

### Seguridad

1. **NUNCA** commitear archivos .env
2. **USAR** wallets de testing para Fuji
3. **ROTAR** keys antes de mainnet
4. **AUDITAR** contratos antes de mainnet

---

## 📝 Changelog

### v1.0.0 (Octubre 2025)
- ✅ MASTER_PLAN.md completo
- ✅ Todos los READMEs creados
- ✅ ARCHITECTURE.md con diagramas
- ✅ .env.example para todos los componentes
- ✅ QUICKSTART.md para setup rápido
- ✅ INDEX.md (este archivo)

---

## 🤝 Contribución

Para contribuir al proyecto:

1. Leer [MASTER_PLAN.md](./MASTER_PLAN.md)
2. Elegir una fase del roadmap
3. Implementar siguiendo arquitectura
4. Testing exhaustivo
5. Pull request con documentación

---

## 📞 Soporte

- **Issues**: GitHub Issues del repositorio
- **Preguntas**: Discord de Ultravioleta DAO
- **Docs**: Este índice y archivos referenciados

---

**Última actualización**: Octubre 2025
**Versión**: 1.0.0
**Autor**: Ultravioleta DAO
