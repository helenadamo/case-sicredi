# Como baixar os CARs manualmente (quando o script automático falhar)

O pipeline **só roda o cruzamento se os 4 polígonos oficiais estiverem em** `raw_data/car/manual/`.

## Opção A — Por imóvel (recomendado, mais leve)

1. Acesse: https://consultapublica.car.gov.br/publico/imoveis/index
2. Selecione o **estado** (RS, PR ou MT)
3. Localize o município e dê zoom até o imóvel
4. Clique no polígono do imóvel
5. Baixe o **shapefile** do imóvel (link na caixa de informações)
6. Salve o `.zip` ou `.shp` em:

```
sicredi_case/raw_data/car/manual/CAR_01/
sicredi_case/raw_data/car/manual/CAR_02/
sicredi_case/raw_data/car/manual/CAR_03/
sicredi_case/raw_data/car/manual/CAR_04/
```

## Opção B — Por município (alternativa)

1. No mesmo site, vá em **Base de Downloads**
2. Selecione o município do imóvel
3. Baixe **Área do Imóvel (AREA_IMOVEL)**
4. Extraia o ZIP e coloque o `.shp` na pasta `manual/CAR_XX/` correspondente

## Códigos deste case

| ID | UF | Código CAR |
|----|-----|------------|
| CAR_01 | RS | RS431940647EE57C13C9749C7994C7046FA96E109 |
| CAR_02 | PR | PR4109401014658F643104BEAAF9A030A42F1D57A |
| CAR_03 | MT | MT5103254B043C12A67EA4522B06A3CF62467D760 |
| CAR_04 | MT | MT5101407324C35ED3C454FE3AA26F7AC45E282C0 |

## Depois de baixar

```bash
cd sicredi_case
.venv\Scripts\activate
python scripts/run_pipeline.py --profile full
```

O script `01_download_car.py` procura primeiro arquivos em `manual/`. Se encontrar os 4, segue com confiança **Alta**.

## Por que o automático pode falhar

- O SICAR exige **captcha** e downloads grandes por estado
- O servidor `consultapublica.car.gov.br` pode dar **timeout** em redes lentas
- O `geoserver.car.gov.br` (WFS) costuma ficar fora do ar

Nesses casos, o download manual pelo site é a forma mais confiável.
