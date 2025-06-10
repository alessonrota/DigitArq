# DigitArq – Documentação Técnica e Conceitual

## 1. Visão Geral

DigitArq é um **programa modular de funções arquivísticas** em Python que abstrai tarefas recorrentes de gestão e preservação de documentos digitais — cópia, conversão, renomeação, relatório fixity, etc.  A arquitetura “plug‑and‑play” permite acrescentar ou remover módulos (plugins) sem alterar o núcleo, favorecendo experimentação em diferentes fluxos de trabalho e desenvolvimento colaborativo.

- **Interface** Tkinter + ttk (paleta cinza neutra)
- **Descoberta de plugins** `src/plugins/*/meta.json` ou entry‑points `pip`
- **Registro de eventos** [P R E M I S 3.0](https://www.loc.gov/standards/premis/) em JSON‑Lines
- **Log de erros** `logs/erro.log` (stack‑trace completo)

---

## 2. Arquitetura Modular

```
DigitArq/                     # projeto
│
├─ src/
│   ├─ digitarq/             # núcleo (GUI + loader)
│   │   ├─ digitarq_main.py  # interface principal
│   │   ├─ context.py        # FORM_CONTEXT (NOBRADI)
│   │   ├─ premis_logger.py  # grava eventos PREMIS
│   │   ├─ plugin_loader.py  # descobre plugins
│   │   └─ erro.py           # configuração do logger
│   └─ plugins/              # plugins de 1ª linha
│       ├─ copiar_mover/
│       ├─ conversao/
│       ├─ renomeacao/
│       └─ relatorio/
└─ logs/
    ├─ erro.log              # exceções
    └─ logs_premis.jsonl     # eventos
```

### 2.1  Autorreconhecimento (*self‑discovery*)

- **Local** `plugin_loader.discover_plugins()` percorre `plugins/*/meta.json`.
- **Remoto (pip)** Pacotes que declaram `entry_points={"digitarq.plugins": ...}` aparecem no menu automaticamente.

Cada plugin importa `context.FORM_CONTEXT` e grava seu próprio evento PREMIS.

```python
# src/plugins/copiar_mover/meta.json
{
  "name": "Cópia/Mover Arquivos",
  "module": "plugins.copiar_mover",
  "entry": "run",
  "description": "Transfere mantendo fixity"
}
```

---

## 3. Metadados PREMIS como pivô de interoperabilidade

| Aspecto                   | Implementação                        | Benefício                 |
| ------------------------- | ------------------------------------ | ------------------------- |
| Identificador de evento   | UUID v4 automático                   | unívoco e rastreável      |
| `eventType`               | *copy, move, convert, name, report…* | aderente a PREMIS 3.0     |
| `eventOutcomeInformation` | *OK* / *FAIL*                        | leitura rápida de sucesso |
| `linkedObjectIdentifier`  | SHA‑256 ou caminho lógico            | vincula objeto digital    |

**Porquê PREMIS?**

- **ISAD(G)** / **ISAAR(CPF)** – descrevem contexto arquivístico; PREMIS descreve eventos de preservação.
- **NOBRADE/NOBRADI** – nomenclatura e codificação; PREMIS armazena fixity, migração, renomeação.
- **MoReq‑SIGAD, e‑ARQ Brasil** – exigem prova de integridade; PREMIS guarda SHA‑256 e verificações periódicas.

### 3.1  Mapeamento para softwares externos

| Software          | Integração possível                                                                                                |
| ----------------- | ------------------------------------------------------------------------------------------------------------------ |
| **AtoM**          | Ingesta de CSV + PREMIS anexado como *event* XML; nomes NOBRADI correspondem a *Identifier*.                       |
| **Archivematica** | Diretório *SIP* pode incluir `logs_premis.jsonl`; fixity é lido na etapa *Verify metadata*.                        |
| **Tainacan**      | Plugin de importação lê CSV exportado pelo módulo **Relatório**, populando Dublin Core; SHA‑256 vira *identifier*. |
| **GEDI/SIGAD**    | Eventos PREMIS satisfazem requisitos de guarda de evidência digital do e‑ARQ.                                      |

---

## 4. Descrição dos Plugins Oficiais

| Plugin           | Função principal                                               | Destaques PREMIS                                                         |
| ---------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------ |
| **Copiar/Mover** | Transfere, calcula SHA‑256 antes/depois, suporta lotes.        | `eventType=copy` ou `move`, outcome *OK/FAIL*, detail sha\_src/sha\_dst. |
| **Conversão**    | Imagem/PDF → PDF, PDF único, compressão JPEG (pikepdf).        | `eventType=convert`, detail quality, hash original.                      |
| **Renomeação**   | Padrão NOBRADI, modos *in‑place / nova pasta / metadados*.     | `eventType=name`, detail novo\_nome, sha256.                             |
| **Relatório**    | Extrai metadados, detecta duplicados/corrompidos, exporta CSV. | `eventType=report`, mime, duplicado?, corrompido?.                       |

---

## 5. Extensão por terceiros

1. Criar `src/plugins/meu_plugin/`
2. Adicionar `meta.json` + `__init__.py` (`run(context)`)
3. (Opcional) publicar no PyPI com entry-point:
   ```toml
   [project.entry-points."digitarq.plugins"]
   meu_plugin = "meu_pkg.mod:run"
   ```

---

## 6. Roadmap

| Versão | Funcionalidade                          | Estado |
| ------ | --------------------------------------- | ------ |
| 1.0    | Core + 4 plugins, PREMIS JSONL          | OK     |
| 1.1    | Executável Windows/Linux                | prev   |
| 1.2    | Backend Qt/PySide opcional              | prev   |
| 2.0    | API REST headless                       | draft  |
| 2.1    | Docker + RabbitMQ                       | idea   |

---

## 7. Considerações finais

DigitArq alia **modularidade dinâmica** e PREMIS, atendendo ISO 14721/15489, Conarq e sistemas SIGAD, GEDI, AtoM. O framework serve como ponte entre digitalização, gestão e preservação, mantendo rastreabilidade e integridade de longo prazo.
