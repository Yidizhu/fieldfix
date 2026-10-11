"""Reviewed fixed UI/report translations. No external services or free-text translation.

Columns are stable source key, Spanish, French, Portuguese. Original evidence,
notes, identifiers and machine-readable states are never replaced by this module.
"""
LOCALES = ('es', 'fr', 'pt')

def catalogue(rows):
    result = {}
    for line in rows.strip().splitlines():
        values = line.split('|')
        if len(values) != 4 or values[0] in result:
            raise ValueError('Invalid or duplicate translation row: ' + values[0])
        result[values[0]] = dict(zip(LOCALES, values[1:]))
    return result

SYSTEM = catalogue('''
三个通道同时缺少数据|Tres canales dejaron de enviar datos a la vez|Trois canaux ont cessé de transmettre ensemble|Três canais deixaram de enviar dados ao mesmo tempo
单支探头持续偏离历史模式|Una sonda se desvía de su patrón histórico|Une sonde s’écarte durablement de son historique|Uma sonda apresenta desvio persistente do padrão histórico
不同土壤水平下的正常变化|Variación normal entre distintos niveles de humedad|Variation normale entre différents niveaux d’humidité|Variação normal entre diferentes níveis de humidade
演示农场 · 北区|Granja de demostración · Sector norte|Ferme de démonstration · Zone nord|Quinta de demonstração · Zona norte
演示农场 · 东区|Granja de demostración · Sector este|Ferme de démonstration · Zone est|Quinta de demonstração · Zona leste
演示农场 · 南区|Granja de demostración · Sector sur|Ferme de démonstration · Zone sud|Quinta de demonstração · Zona sul
没有可供分析的设备观测。|No hay observaciones de dispositivos para analizar.|Aucune observation de dispositif n’est disponible.|Não há observações de dispositivos para analisar.
未收到有效设备列表。|No se recibió una lista válida de dispositivos.|Aucune liste valide de dispositifs reçue.|Não foi recebida uma lista válida de dispositivos.
先导入带时间戳的观测和设备连接关系。|Importe primero observaciones con fecha y hora y las conexiones entre dispositivos.|Importez d’abord les observations horodatées et les connexions des dispositifs.|Importe primeiro observações com data e hora e as ligações dos dispositivos.
没有有效的设备观测。|No hay observaciones válidas de dispositivos.|Aucune observation valide de dispositif.|Não há observações válidas de dispositivos.
设备输入格式不完整。|El formato de entrada del dispositivo está incompleto.|Le format des données du dispositif est incomplet.|O formato dos dados do dispositivo está incompleto.
检查设备列表与时间戳字段。|Revise la lista de dispositivos y las marcas de tiempo.|Vérifiez la liste des dispositifs et les horodatages.|Verifique a lista de dispositivos e as marcas de tempo.
共同缺数与公共链路问题相容，但不能据此确认采集器故障，也不能认定所有探头损坏。|La falta simultánea de datos puede corresponder a un problema de conexión compartida. No confirma un fallo del concentrador ni daños en todas las sondas.|L’absence simultanée de données peut correspondre à un problème de liaison commune. Elle ne prouve ni une panne de la passerelle ni des dommages à toutes les sondes.|A ausência simultânea de dados pode indicar um problema de ligação comum. Não confirma avaria do concentrador nem danos em todas as sondas.
多支设备同步缺数，优先检查共享连接。|Varios dispositivos presentan lagunas simultáneas. Revise primero la conexión compartida.|Plusieurs dispositifs présentent des lacunes simultanées. Vérifiez d’abord la liaison commune.|Vários dispositivos têm falhas de dados simultâneas. Verifique primeiro a ligação comum.
核查采集器供电、网络与最近维护记录。|Revise la alimentación, la red y el mantenimiento reciente del concentrador.|Vérifiez l’alimentation, le réseau et l’entretien récent de la passerelle.|Verifique a alimentação, a rede e a manutenção recente do concentrador.
现场检查公共链路后，观察各通道是否恢复。|Inspeccione la conexión compartida en campo y compruebe si cada canal vuelve a enviar datos.|Inspectez la liaison commune sur place, puis vérifiez la reprise de chaque canal.|Inspecione a ligação comum no local e verifique se cada canal volta a transmitir.
尚无证据支持逐支换新；恢复上传后再评估读数。|No hay evidencia para sustituir todas las sondas. Reevalúe las lecturas cuando se restablezca el envío.|Rien ne justifie de remplacer chaque sonde. Réévaluez les mesures après la reprise des transmissions.|Não há evidência para substituir todas as sondas. Reavalie as leituras após o envio ser restabelecido.
异常判定使用每支设备自身的历史小时基线，没有把不同土壤水平直接互相比高低。|Cada dispositivo se compara con su propia referencia horaria histórica, sin comparar directamente distintos niveles de humedad del suelo.|Chaque dispositif est comparé à sa propre référence horaire historique, sans comparer directement des niveaux d’humidité différents.|Cada dispositivo é comparado com a sua própria referência horária histórica, sem comparar diretamente diferentes níveis de humidade do solo.
持续偏差可能来自真实土壤变化、安装接触、设备问题或基线失配；当前证据不能确认硬件损坏。|El desvío persistente puede deberse al suelo, al contacto de instalación, al dispositivo o a una referencia inadecuada. No confirma daños físicos.|L’écart persistant peut venir du sol, du contact de pose, du dispositif ou d’une référence inadaptée. Il ne confirme pas un dommage matériel.|O desvio persistente pode resultar do solo, do contacto de instalação, do dispositivo ou de uma referência inadequada. Não confirma danos físicos.
另外存在末段缺数的设备，相关连接仍需单独核查。|Otros dispositivos también presentan lagunas recientes; revise sus conexiones por separado.|D’autres dispositifs ont aussi des lacunes récentes ; vérifiez leurs connexions séparément.|Outros dispositivos também têm falhas recentes de dados; verifique as ligações separadamente.
发现持续读数偏差，需要结合现场信息复核。|Se detectó un desvío persistente que requiere revisión con información de campo.|Un écart persistant nécessite une vérification avec les informations du terrain.|Foi detetado um desvio persistente que exige revisão com informação do terreno.
先核对降雨、灌溉和近期安装或维护记录。|Revise primero la lluvia, el riego y las instalaciones o el mantenimiento recientes.|Vérifiez d’abord la pluie, l’irrigation et les interventions récentes.|Verifique primeiro a chuva, a rega e as instalações ou manutenções recentes.
检查探头接触与连接；必要时使用独立测量作对照。|Revise el contacto y las conexiones de la sonda; compare con una medición independiente si es necesario.|Vérifiez le contact et les connexions de la sonde ; comparez avec une mesure indépendante si nécessaire.|Verifique o contacto e as ligações da sonda; compare com uma medição independente se necessário.
记录技术员结论后，再决定观察、维修、保修或替换。|Registre las conclusiones del técnico antes de elegir observación, reparación, garantía o sustitución.|Consignez les conclusions du technicien avant de choisir observation, réparation, garantie ou remplacement.|Registe as conclusões do técnico antes de escolher observação, reparação, garantia ou substituição.
部分设备的采集器关系未知；不能把同时缺数直接归因于同一个采集器。|Se desconoce qué concentrador usan algunos dispositivos. Las lagunas simultáneas no prueban una causa común.|La passerelle de certains dispositifs est inconnue. Des lacunes simultanées ne prouvent pas une cause commune.|Desconhece-se o concentrador de alguns dispositivos. Falhas simultâneas de dados não provam uma causa comum.
不能把缺失观测解释成正常，也不能直接解释为硬件损坏。|La ausencia de observaciones no demuestra funcionamiento normal ni daños físicos.|L’absence d’observations ne prouve ni un fonctionnement normal ni un dommage matériel.|A ausência de observações não prova funcionamento normal nem danos físicos.
现有数据不足以完成读数判断。|No hay datos suficientes para evaluar las lecturas.|Les données sont insuffisantes pour évaluer les mesures.|Não há dados suficientes para avaliar as leituras.
补充逐小时观测与真实设备连接关系。|Añada observaciones horarias y conexiones verificadas entre dispositivos.|Ajoutez les observations horaires et les connexions vérifiées des dispositifs.|Acrescente observações horárias e ligações verificadas dos dispositivos.
对缺数设备先检查上传和供电情况。|En los dispositivos sin datos, revise primero el envío y la alimentación.|Pour les dispositifs sans données, vérifiez d’abord la transmission et l’alimentation.|Nos dispositivos sem dados, verifique primeiro o envio e a alimentação.
本次演示规则未发现持续异常。|Las reglas de demostración no detectaron una anomalía persistente.|Les règles de démonstration n’ont détecté aucune anomalie persistante.|As regras de demonstração não detetaram anomalias persistentes.
没有检测到连续6小时同向超过各自历史基线阈值的读数。|Ninguna lectura superó su umbral histórico en la misma dirección durante 6 horas consecutivas.|Aucune mesure n’a dépassé son seuil historique dans le même sens pendant 6 heures consécutives.|Nenhuma leitura excedeu o seu limiar histórico na mesma direção durante 6 horas consecutivas.
未触发规则不等于设备完全健康；缓慢变化或其他类型故障可能未被本方法覆盖。|La ausencia de alertas no demuestra que el dispositivo esté sano. El método puede omitir cambios graduales u otros fallos.|L’absence d’alerte ne prouve pas le bon état du dispositif. La méthode peut manquer des évolutions lentes ou d’autres pannes.|A ausência de alertas não prova que o dispositivo esteja saudável. O método pode não detetar mudanças lentas ou outras avarias.
继续观察并保留灌溉、天气及维护记录。|Continúe observando y conserve los registros de riego, tiempo y mantenimiento.|Poursuivez l’observation et conservez les relevés d’irrigation, de météo et d’entretien.|Continue a observar e guarde os registos de rega, meteorologia e manutenção.
如有现场异常，仍应独立检查。|Investigue de forma independiente cualquier anomalía observada en campo.|Examinez indépendamment toute anomalie constatée sur place.|Investigue de forma independente qualquer anomalia observada no local.
AI 发现多支设备停止上传，共享连接值得先检查。|La IA detectó que varios dispositivos dejaron de enviar datos. Revise primero la conexión compartida.|L’IA a détecté l’arrêt des transmissions de plusieurs dispositifs. Vérifiez d’abord la liaison commune.|A IA detetou que vários dispositivos deixaram de enviar dados. Verifique primeiro a ligação comum.
AI 发现持续读数偏移，需要结合现场情况复核。|La IA detectó un desvío persistente que requiere revisión con el contexto de campo.|L’IA a détecté un décalage persistant à vérifier avec le contexte du terrain.|A IA detetou um desvio persistente que exige revisão com o contexto do terreno.
AI 发现读数长时间不变，需要核对现场变化和设备。|La IA detectó lecturas constantes durante mucho tiempo. Revise el entorno y el dispositivo.|L’IA a détecté des mesures longtemps constantes. Vérifiez les conditions locales et le dispositif.|A IA detetou leituras constantes durante muito tempo. Verifique o ambiente e o dispositivo.
AI 暂未发现所学范围内的异常模式。|La IA no detectó patrones inusuales dentro de su ámbito de aprendizaje.|L’IA n’a détecté aucun schéma inhabituel dans son domaine d’apprentissage.|A IA não detetou padrões invulgares no âmbito do que aprendeu.
AI 发现上传中断，恢复数据后再判断读数。|La IA detectó una interrupción de datos. Restablezca el envío antes de evaluar las lecturas.|L’IA a détecté une interruption des données. Rétablissez la transmission avant d’évaluer les mesures.|A IA detetou uma interrupção de dados. Restabeleça o envio antes de avaliar as leituras.
部分观测不足或不适用，AI 暂不能给出完整判断。|Algunas observaciones son insuficientes o quedan fuera del ámbito. La IA no puede completar la evaluación.|Certaines observations sont insuffisantes ou hors périmètre. L’IA ne peut pas terminer l’évaluation.|Algumas observações são insuficientes ou estão fora do âmbito. A IA não pode concluir a avaliação.
AI 分析暂不可用，请恢复分析后再批准付费处理。|El análisis de IA no está disponible. Restablézcalo antes de aprobar un servicio de pago.|L’analyse IA est indisponible. Rétablissez-la avant d’approuver une intervention payante.|A análise de IA está indisponível. Restabeleça-a antes de aprovar um serviço pago.
AI 与独立规则的结果不一致，需要补充检查。|La IA y las comprobaciones independientes discrepan. Se requiere más investigación.|L’IA et les contrôles indépendants divergent. Des vérifications supplémentaires sont nécessaires.|A IA e as verificações independentes discordam. São necessárias mais verificações.
''')

METHODS = catalogue('''
baseline|Reglas de demostración y referencia temporal: cada dispositivo se calibra con sus primeras 48 observaciones horarias; las siguientes solo se usan para detección. Se necesitan 6 puntos válidos consecutivos desviados en la misma dirección. Solo se agrupan dispositivos con concentrador compartido conocido y lagunas que empiezan cerca. No se usan etiquetas de escenario. Son pistas, no un diagnóstico de daños físicos.|Règles de démonstration et référence temporelle : les 48 premières observations horaires servent à calibrer chaque dispositif ; les suivantes servent uniquement à la détection. Une alerte exige 6 points valides consécutifs déviant dans le même sens. Seuls les dispositifs avec une passerelle commune connue et des lacunes proches sont regroupés. Les étiquettes de scénario ne sont pas utilisées. Ce sont des pistes, pas un diagnostic matériel.|Regras de demonstração e referência temporal: as primeiras 48 observações horárias calibram cada dispositivo; as seguintes servem apenas para deteção. Um alerta exige 6 pontos válidos consecutivos desviados na mesma direção. Só se agrupam dispositivos com concentrador comum conhecido e falhas de dados próximas. Não são usadas etiquetas de cenário. São pistas, não um diagnóstico de danos físicos.
ai|La IA ejecuta una regresión logística multiclase entrenada con secuencias sintéticas sobre las observaciones del caso. Las reglas estadísticas independientes comprueban los datos y las conexiones compartidas. Los patrones no distinguen cambios reales del suelo de problemas del dispositivo, ni aprueban reparaciones o pagos.|L’IA applique une régression logistique multiclasse entraînée sur des séquences synthétiques aux observations du dossier. Des règles statistiques indépendantes vérifient les données et les liaisons communes. Ces schémas ne distinguent pas les changements réels du sol des problèmes du dispositif et n’autorisent ni réparation ni paiement.|A IA executa uma regressão logística multiclasse treinada com sequências sintéticas sobre as observações do caso. Regras estatísticas independentes verificam os dados e as ligações comuns. Os padrões não distinguem alterações reais do solo de problemas do dispositivo, nem aprovam reparações ou pagamentos.
''')
PATTERNS = catalogue('''
0|{count} dispositivos comparten el concentrador conocido {gateway}: {names}.|{count} dispositifs partagent la passerelle connue {gateway} : {names}.|{count} dispositivos partilham o concentrador conhecido {gateway}: {names}.
1|Las lagunas empiezan cerca de {start}, con una diferencia máxima de {hours} hora(s).|Les lacunes commencent vers {start}, avec au plus {hours} heure(s) d’écart.|As falhas de dados começam perto de {start}, com uma diferença máxima de {hours} hora(s).
2|Faltan respectivamente {counts} observaciones horarias consecutivas al final. No se interpolaron los datos ausentes.|Il manque respectivement {counts} observations horaires consécutives en fin de série. Les données manquantes n’ont pas été interpolées.|Faltam respetivamente {counts} observações horárias consecutivas no fim. Os dados em falta não foram interpolados.
3|{name}: {calibration} puntos históricos válidos para calibración y {detection} puntos válidos posteriores para detección. El desvío más largo en la misma dirección sobre el umbral de demostración ±{threshold} puntos porcentuales duró {run} horas consecutivas.|{name} : {calibration} points historiques valides pour la calibration et {detection} points valides suivants pour la détection. Le dépassement dans le même sens du seuil de démonstration ±{threshold} points de pourcentage a duré au maximum {run} heures consécutives.|{name}: {calibration} pontos históricos válidos para calibração e {detection} pontos válidos seguintes para deteção. O desvio mais longo na mesma direção acima do limiar de demonstração ±{threshold} pontos percentuais durou {run} horas consecutivas.
4|{name}: los intervalos no cumplen el requisito de datos horarios de esta demostración.|{name} : les intervalles ne respectent pas l’exigence horaire de cette démonstration.|{name}: os intervalos não cumprem o requisito de dados horários desta demonstração.
5|{name}: faltan las últimas {count} observaciones horarias consecutivas.|{name} : les {count} dernières observations horaires consécutives manquent.|{name}: faltam as últimas {count} observações horárias consecutivas.
6|{name}: faltan datos históricos de calibración o datos posteriores de detección.|{name} : données de calibration historique ou de détection ultérieure insuffisantes.|{name}: faltam dados históricos de calibração ou dados posteriores de deteção.
7|Se revisaron {count} dispositivos por separado, con ventanas distintas para calibración y detección.|{count} dispositifs vérifiés séparément, avec des fenêtres distinctes de calibration et de détection.|Foram verificados {count} dispositivos separadamente, com janelas distintas para calibração e deteção.
''')
MISC = catalogue('''
probe|Sonda |Sonde |Sonda 
original_evidence|Evidencia original (sin traducción disponible): |Élément original (traduction indisponible) : |Evidência original (tradução indisponível): 
original_event|Evento registrado (texto original): |Événement consigné (texte original) : |Evento registado (texto original): 
error|No se pudo completar la acción. Revise la solicitud o inténtelo más tarde.|L’action n’a pas pu aboutir. Vérifiez la demande ou réessayez plus tard.|Não foi possível concluir a ação. Verifique o pedido ou tente mais tarde.
''')
RECOVERY = catalogue('''
pass|Las observaciones sintéticas tras el servicio cumplen todas las comprobaciones fijas. Es una demostración, no evidencia validada de campo ni una certificación de reparación.|Les observations synthétiques après intervention satisfont tous les contrôles fixes. Il s’agit d’une démonstration, pas de données de terrain validées ni d’une certification de réparation.|As observações sintéticas após o serviço cumprem todas as verificações fixas. É uma demonstração, não evidência de campo validada nem uma certificação de reparação.
fail|Al menos una comprobación evaluable de las observaciones sintéticas falla. No se ha demostrado la recuperación; revise los fallos. Esto no determina la causa de una avería real.|Au moins un contrôle évaluable des observations synthétiques échoue. Le rétablissement n’est pas démontré ; examinez les échecs. Cela n’établit pas la cause d’une panne réelle.|Pelo menos uma verificação avaliável das observações sintéticas falha. A recuperação não foi demonstrada; reveja as falhas. Isto não determina a causa de uma avaria real.
insufficient|Las observaciones sintéticas no tienen cobertura válida o variación de referencia suficiente para evaluar la recuperación. La falta de evidencia no equivale a una reparación exitosa.|Les observations synthétiques n’offrent pas assez de couverture valide ou de variation de référence pour évaluer le rétablissement. Une preuve manquante ne vaut pas réparation réussie.|As observações sintéticas não têm cobertura válida ou variação de referência suficiente para avaliar a recuperação. A falta de evidência não equivale a uma reparação bem-sucedida.
''')
ERRORS = catalogue('''
AI 证据尚未就绪，不能进入替换、保修或新交易；请先补齐证据。|La evidencia de IA no está lista. Complétela antes de sustituir, tramitar garantía o iniciar una transacción.|Les éléments IA ne sont pas prêts. Complétez-les avant remplacement, garantie ou nouvelle transaction.|A evidência de IA não está pronta. Complete-a antes de substituição, garantia ou nova transação.
AI 证据标识不完整，不能进入替换、保修或新交易。|Los identificadores de evidencia de IA están incompletos. Sustitución, garantía y nuevas transacciones bloqueadas.|Les identifiants des éléments IA sont incomplets. Remplacement, garantie et nouvelles transactions bloqués.|Os identificadores da evidência de IA estão incompletos. Substituição, garantia e novas transações bloqueadas.
当前人工复核没有绑定可用 AI 证据；请重新复核后再批准新交易。|Esta revisión no está vinculada a evidencia de IA utilizable. Repítala antes de aprobar una transacción.|Cette vérification n’est pas liée à des éléments IA utilisables. Recommencez-la avant d’approuver une transaction.|Esta revisão não está vinculada a evidência de IA utilizável. Repita-a antes de aprovar uma transação.
AI 模型或案件证据已变化；请重新进行人工复核后再批准新交易。|Cambió el modelo de IA o la evidencia del caso. Repita la revisión humana antes de aprobar una transacción.|Le modèle IA ou les éléments du dossier ont changé. Répétez la vérification humaine avant d’approuver une transaction.|O modelo de IA ou a evidência do caso mudou. Repita a revisão humana antes de aprovar uma transação.
仅允许本地访问。|Solo se permite acceso local.|Seul l’accès local est autorisé.|Só é permitido acesso local.
未找到页面。|Página no encontrada.|Page introuvable.|Página não encontrada.
请刷新本地页面后再操作。|Actualice la página local antes de repetir la acción.|Actualisez la page locale avant de réessayer.|Atualize a página local antes de repetir a ação.
不允许跨站操作。|No se permiten solicitudes entre sitios.|Les requêtes intersites ne sont pas autorisées.|Não são permitidos pedidos entre sites.
请求格式必须为 JSON。|La solicitud debe usar JSON.|La demande doit utiliser JSON.|O pedido deve usar JSON.
操作不存在。|Esta acción no existe.|Cette action n’existe pas.|Esta ação não existe.
请求长度无效。|La longitud de la solicitud no es válida.|La longueur de la demande est invalide.|O tamanho do pedido é inválido.
请求内容无效。|El contenido de la solicitud no es válido.|Le contenu de la demande est invalide.|O conteúdo do pedido é inválido.
处理未完成。请检查服务日志或稍后重试。|No se pudo completar la acción. Revise los registros del servicio o inténtelo más tarde.|L’action n’a pas abouti. Consultez les journaux du service ou réessayez plus tard.|Não foi possível concluir a ação. Verifique os registos do serviço ou tente mais tarde.
案件不存在。|Caso no encontrado.|Dossier introuvable.|Caso não encontrado.
已有交易记录，不能覆盖前序复核。|Ya existe una transacción; no se puede sobrescribir la revisión anterior.|Une transaction existe déjà ; la vérification précédente ne peut pas être remplacée.|Já existe uma transação; a revisão anterior não pode ser substituída.
请填写 8–1000 字的检查记录。|Escriba una nota de inspección de 8–1000 caracteres.|Saisissez une note d’inspection de 8–1000 caractères.|Escreva uma nota de inspeção com 8–1000 caracteres.
请选择有效处理方式。|Elija una opción de gestión válida.|Choisissez une option de traitement valide.|Escolha uma opção de tratamento válida.
当前证据不支持进入单支更换或保修流程。|La evidencia actual no justifica sustituir una sola sonda ni tramitar su garantía.|Les éléments actuels ne justifient pas le remplacement ou la garantie d’une seule sonde.|A evidência atual não justifica substituir uma só sonda nem acionar a garantia.
需要明确确认这是演练中的人工检查记录。|Confirme explícitamente que es una inspección humana de demostración.|Confirmez explicitement qu’il s’agit d’une inspection humaine de démonstration.|Confirme explicitamente que é uma inspeção humana de demonstração.
先记录人工检查并选择过保替换。|Registre primero una inspección humana y seleccione sustitución fuera de garantía.|Consignez d’abord une inspection humaine et choisissez le remplacement hors garantie.|Registe primeiro uma inspeção humana e selecione substituição fora da garantia.
采购需要明确批准。|La compra requiere aprobación explícita.|L’achat exige une approbation explicite.|A compra exige aprovação explícita.
未通过人工复核与采购批准，不能执行交易。|La transacción requiere revisión humana y aprobación de compra.|La transaction exige une vérification humaine et une approbation d’achat.|A transação exige revisão humana e aprovação da compra.
已有 Sandbox 订单，不能改成本地演练。|Ya existe un pedido Sandbox; no puede convertirse en un ensayo local.|Une commande Sandbox existe déjà ; elle ne peut pas devenir un essai local.|Já existe uma encomenda Sandbox; não pode ser convertida num ensaio local.
本案已有本地演练记录。使用另一份测试数据库运行 Sandbox。|Este caso ya tiene un ensayo local. Use otra base de datos de prueba para Sandbox.|Ce dossier contient déjà un essai local. Utilisez une autre base de test pour Sandbox.|Este caso já tem um ensaio local. Use outra base de dados de teste para Sandbox.
没有可核验的 Sandbox 订单。|No hay un pedido Sandbox que verificar.|Aucune commande Sandbox à vérifier.|Não há encomenda Sandbox para verificar.
先完成案件复核。|Complete primero la revisión del caso.|Terminez d’abord la vérification du dossier.|Conclua primeiro a revisão do caso.
采购流程尚未完成。|El proceso de compra no está completo.|Le processus d’achat n’est pas terminé.|O processo de compra não está concluído.
保修为申请草稿，尚未接入商家处理与验收。|La garantía es un borrador; no incluye gestión ni aceptación del comerciante.|La demande de garantie est un brouillon ; le traitement et la réception par le marchand ne sont pas intégrés.|O pedido de garantia é um rascunho; o tratamento e a aceitação pelo comerciante não estão integrados.
请确认模拟复查并填写 8–1000 字观察记录。|Confirme la revisión simulada y escriba una observación de 8–1000 caracteres.|Confirmez la vérification simulée et saisissez une observation de 8–1000 caractères.|Confirme a revisão simulada e escreva uma observação com 8–1000 caracteres.
PayPal Sandbox 未完成请求。请检查配置或稍后重试；不要另建重复订单。|PayPal Sandbox no completó la solicitud. Revise la configuración o reintente más tarde; no duplique el pedido.|PayPal Sandbox n’a pas terminé la demande. Vérifiez la configuration ou réessayez plus tard ; ne dupliquez pas la commande.|O PayPal Sandbox não concluiu o pedido. Verifique a configuração ou tente mais tarde; não duplique a encomenda.
尚未配置 PayPal Sandbox 测试凭据。|No se han configurado las credenciales de prueba de PayPal Sandbox.|Les identifiants de test PayPal Sandbox ne sont pas configurés.|As credenciais de teste do PayPal Sandbox não estão configuradas.
Sandbox 授权失败。|Falló la autenticación de Sandbox.|Échec de l’authentification Sandbox.|Falha na autenticação Sandbox.
Sandbox 未返回有效的测试付款链接。|Sandbox no devolvió un enlace de pago de prueba válido.|Sandbox n’a pas renvoyé de lien de paiement de test valide.|O Sandbox não devolveu uma ligação válida para pagamento de teste.
订单编号无效。|El identificador del pedido no es válido.|L’identifiant de commande est invalide.|O identificador da encomenda é inválido.
买家尚未完成批准，订单未捕获。|Falta la aprobación del comprador. No se ha cobrado el pedido.|L’acheteur n’a pas terminé l’approbation. La commande n’a pas été débitée.|Falta a aprovação do comprador. A encomenda não foi cobrada.
订单编号不一致，需要人工复核。|El identificador del pedido no coincide; se requiere revisión humana.|L’identifiant de commande ne correspond pas ; vérification humaine requise.|O identificador da encomenda não coincide; é necessária revisão humana.
订单明细数量不符合预期。|La cantidad de unidades de compra no coincide con lo esperado.|Le nombre d’unités d’achat ne correspond pas à la commande attendue.|O número de unidades de compra não corresponde ao esperado.
订单与案件不一致，需要人工复核。|El pedido no corresponde al caso; se requiere revisión humana.|La commande ne correspond pas au dossier ; vérification humaine requise.|A encomenda não corresponde ao caso; é necessária revisão humana.
订单金额或币种不符合预期。|El importe o la moneda del pedido no coincide con el presupuesto.|Le montant ou la devise ne correspond pas au devis.|O valor ou a moeda da encomenda não corresponde ao orçamento.
付款状态尚未完成。|El pago aún no está completado.|Le paiement n’est pas encore terminé.|O pagamento ainda não está concluído.
付款记录数量不符合预期。|El número de registros de pago no es el esperado.|Le nombre d’enregistrements de paiement est inattendu.|O número de registos de pagamento não é o esperado.
付款金额、币种或状态不符合预期。|El importe, la moneda o el estado del pago no coincide con lo esperado.|Le montant, la devise ou l’état du paiement est inattendu.|O valor, a moeda ou o estado do pagamento não corresponde ao esperado.
未通过人工复核与报价批准，不能执行交易。|La transacción requiere revisión humana y aprobación del presupuesto.|La transaction exige une vérification humaine et l’approbation du devis.|A transação exige revisão humana e aprovação do orçamento.
原请求已超过安全重试期限；请核对交易或人工处理，不能新建重复订单。|Venció el plazo de reintento seguro. Consulte la transacción o solicite revisión manual; no duplique el pedido.|Le délai de nouvelle tentative sûre est dépassé. Vérifiez la transaction ou demandez un traitement manuel ; ne dupliquez pas la commande.|O prazo de repetição segura expirou. Consulte a transação ou peça revisão manual; não duplique a encomenda.
旧版交易记录仅供查阅，请使用新演示案件。|Las transacciones antiguas son de solo lectura. Use un caso de demostración nuevo.|Les anciennes transactions sont en lecture seule. Utilisez un nouveau dossier de démonstration.|As transações antigas são só de leitura. Use um novo caso de demonstração.
上一笔请求结果尚未确定；请重试同一操作或核对原交易。|La solicitud anterior sigue sin resolverse. Repita la misma operación o consulte la transacción original.|La demande précédente reste indéterminée. Réessayez la même opération ou vérifiez la transaction initiale.|O pedido anterior continua por resolver. Repita a mesma operação ou consulte a transação original.
报价需要明确批准。|El presupuesto requiere aprobación explícita.|Le devis exige une approbation explicite.|O orçamento exige aprovação explícita.
本地演练与 Sandbox 交易不能混用，请使用独立测试案件。|No mezcle ensayos locales y transacciones Sandbox. Use casos de prueba separados.|Ne mélangez pas essais locaux et transactions Sandbox. Utilisez des dossiers de test distincts.|Não misture ensaios locais e transações Sandbox. Use casos de teste separados.
没有可核验的授权订单。|No hay un pedido de autorización que verificar.|Aucune commande d’autorisation à vérifier.|Não há encomenda de autorização para verificar.
扣款需要再次明确确认金额与恢复复核结果。|El cobro exige confirmar otra vez el importe y la revisión de recuperación.|Le débit exige de confirmer à nouveau le montant et la vérification du rétablissement.|A cobrança exige nova confirmação do valor e da revisão da recuperação.
恢复证据尚未通过检查和人工复核，禁止扣款。|La evidencia de recuperación no superó las comprobaciones y la revisión humana. Cobro bloqueado.|Les preuves de rétablissement n’ont pas passé les contrôles et la vérification humaine. Débit bloqué.|A evidência de recuperação não passou as verificações e a revisão humana. Cobrança bloqueada.
当前授权不可扣款。|Esta autorización no permite el cobro.|Cette autorisation ne permet pas le débit.|Esta autorização não permite cobrança.
撤销授权需要明确确认。|Anular la autorización requiere confirmación explícita.|L’annulation exige une confirmation explicite.|Anular a autorização exige confirmação explícita.
当前授权不可撤销；请先核对是否已扣款。|No se puede anular esta autorización. Compruebe si ya se cobró.|Cette autorisation ne peut pas être annulée. Vérifiez si elle a déjà été débitée.|Esta autorização não pode ser anulada. Verifique se já foi cobrada.
本地演练没有可查询的 PayPal 交易。|Un ensayo local no tiene una transacción PayPal que consultar.|Un essai local n’a aucune transaction PayPal à consulter.|Um ensaio local não tem transação PayPal para consultar.
缺少已核验的授权编号。|Falta un identificador de autorización verificado.|L’identifiant d’autorisation vérifié manque.|Falta um identificador de autorização verificado.
请先完成授权；已结算或撤销的记录不可修改恢复证据。|Complete primero la autorización. No se puede cambiar la evidencia tras el cobro o la anulación.|Terminez d’abord l’autorisation. Les preuves ne peuvent plus changer après débit ou annulation.|Conclua primeiro a autorização. A evidência não pode mudar após cobrança ou anulação.
请选择有效的模拟恢复数据场景。|Elija un escenario válido de recuperación sintética.|Choisissez un scénario de rétablissement synthétique valide.|Escolha um cenário válido de recuperação sintética.
恢复证据尚未通过检查，不能确认恢复。|La evidencia no superó las comprobaciones; no se puede aceptar la recuperación.|Les preuves n’ont pas passé les contrôles ; le rétablissement ne peut pas être accepté.|A evidência não passou as verificações; a recuperação não pode ser aceite.
旧版直接扣款订单不可用于先授权后扣款流程。|Un pedido antiguo de cobro directo no sirve para el flujo de autorización previa.|Une ancienne commande à débit direct ne convient pas au parcours avec autorisation préalable.|Uma encomenda antiga de cobrança direta não serve para o fluxo com autorização prévia.
买家尚未批准此授权订单；尚未扣款。|El comprador aún no aprobó la autorización. No se ha cobrado.|L’acheteur n’a pas encore approuvé cette autorisation. Aucun débit effectué.|O comprador ainda não aprovou a autorização. Não houve cobrança.
订单授权记录不完整，需要人工核查。|El registro de autorización está incompleto; requiere revisión humana.|L’enregistrement d’autorisation est incomplet ; vérification humaine requise.|O registo de autorização está incompleto; exige revisão humana.
授权编号与本案不一致，需要人工核查。|La autorización no corresponde al caso; requiere revisión humana.|L’autorisation ne correspond pas au dossier ; vérification humaine requise.|A autorização não corresponde ao caso; exige revisão humana.
授权金额或币种不符合预期。|El importe o la moneda autorizados no coincide con el presupuesto aprobado.|Le montant ou la devise autorisés ne correspond pas au devis approuvé.|O valor ou a moeda autorizados não corresponde ao orçamento aprovado.
授权状态不适用于本演示，需要人工核查。|El estado de autorización no es compatible con esta demostración; requiere revisión humana.|Cet état d’autorisation n’est pas pris en charge ; vérification humaine requise.|O estado da autorização não é compatível com esta demonstração; exige revisão humana.
授权有效期不完整，需要人工核查。|La vigencia de la autorización está incompleta; requiere revisión humana.|La validité de l’autorisation est incomplète ; vérification humaine requise.|A validade da autorização está incompleta; exige revisão humana.
授权尚不可扣款；请先核对交易状态。|La autorización aún no permite cobrar. Consulte primero su estado.|L’autorisation ne permet pas encore le débit. Vérifiez d’abord son état.|A autorização ainda não permite cobrar. Consulte primeiro o estado.
授权已超过本演示的三天扣款期限；请人工处理，不能自动重新授权。|La autorización superó el plazo de cobro de tres días de esta demostración. Requiere gestión manual, sin reautorización automática.|L’autorisation dépasse le délai de débit de trois jours de cette démonstration. Traitement manuel requis, sans renouvellement automatique.|A autorização ultrapassou o prazo de cobrança de três dias desta demonstração. Exige tratamento manual, sem reautorização automática.
未取得可核查的扣款编号；请保持本案并核对原交易。|No se recibió un identificador de cobro verificable. Conserve el caso y consulte la transacción original.|Aucun identifiant de débit vérifiable reçu. Conservez le dossier et vérifiez la transaction initiale.|Não foi recebido um identificador de cobrança verificável. Mantenha o caso e consulte a transação original.
尚未核实授权撤销；请核对原交易，不要新建订单。|No se verificó la anulación. Consulte la transacción original; no cree otro pedido.|L’annulation n’est pas vérifiée. Consultez la transaction initiale ; ne créez pas de nouvelle commande.|A anulação não foi verificada. Consulte a transação original; não crie outra encomenda.
扣款记录不属于本案授权。|El cobro no pertenece a la autorización de este caso.|Le débit n’appartient pas à l’autorisation de ce dossier.|A cobrança não pertence à autorização deste caso.
本地演练不连接 PayPal。请使用本地演练操作。|El ensayo local no conecta con PayPal. Use la acción de ensayo local.|L’essai local ne se connecte pas à PayPal. Utilisez l’action d’essai local.|O ensaio local não se liga ao PayPal. Use a ação de ensaio local.
''')
HISTORY = catalogue('''
批准模拟目录 FF-Soil-01，NZD 25.00；演示政策设为过保，兼容性为模拟声明。|Artículo simulado FF-Soil-01 aprobado, NZD 25.00. La demostración lo considera fuera de garantía; la compatibilidad es simulada.|Article simulé FF-Soil-01 approuvé, NZD 25.00. La démonstration le considère hors garantie ; compatibilité simulée.|Artigo simulado FF-Soil-01 aprovado, NZD 25.00. A demonstração considera-o fora da garantia; compatibilidade simulada.
本地交易演练已记录；未调用 PayPal，未产生付款。|Ensayo de transacción local registrado. Sin llamada a PayPal ni pago.|Essai de transaction local consigné. Aucun appel PayPal ni paiement.|Ensaio de transação local registado. Sem chamada ao PayPal nem pagamento.
Sandbox 测试订单已创建，等待买家批准。|Pedido de prueba Sandbox creado; esperando aprobación del comprador.|Commande de test Sandbox créée ; approbation de l’acheteur attendue.|Encomenda de teste Sandbox criada; a aguardar aprovação do comprador.
服务端核验 Sandbox 捕获已完成；设备仍待安装与复查。|El servidor verificó el cobro Sandbox. La instalación y revisión del dispositivo siguen pendientes.|Le serveur a vérifié le débit Sandbox. Installation et vérification du dispositif restent en attente.|O servidor verificou a cobrança Sandbox. A instalação e a revisão do dispositivo continuam pendentes.
Sandbox 请求已开始；结果未核实前禁止执行相反操作。|Solicitud Sandbox iniciada. Se bloquean acciones incompatibles hasta verificar el resultado.|Demande Sandbox lancée. Les actions contradictoires sont bloquées jusqu’à vérification du résultat.|Pedido Sandbox iniciado. Ações incompatíveis ficam bloqueadas até verificar o resultado.
已批准模拟服务报价 NZD 25.00；监测服务商为卖方，农场为买方。|Presupuesto simulado de NZD 25.00 aprobado. El proveedor de monitoreo vende y la granja compra.|Devis simulé de NZD 25.00 approuvé. Le prestataire de surveillance vend et la ferme achète.|Orçamento simulado de NZD 25.00 aprovado. O prestador de monitorização vende e a quinta compra.
本地授权演练已记录；未调用 PayPal，未冻结或扣取任何款项。|Ensayo de autorización local registrado. Sin llamada a PayPal; no se retuvieron ni cobraron fondos.|Essai d’autorisation local consigné. Aucun appel PayPal ; aucun fonds réservé ou débité.|Ensaio de autorização local registado. Sem chamada ao PayPal; nenhum valor foi retido ou cobrado.
Sandbox 授权订单已创建，等待测试买家批准；尚未扣款。|Pedido de autorización Sandbox creado; espera aprobación del comprador de prueba. Sin cobro.|Commande d’autorisation Sandbox créée ; approbation de l’acheteur test attendue. Aucun débit.|Encomenda de autorização Sandbox criada; aguarda aprovação do comprador de teste. Sem cobrança.
已重新查询 Sandbox 原交易；付款状态与维修状态分别保留。|Se consultó de nuevo la transacción Sandbox. Los estados de pago y reparación siguen separados.|Transaction Sandbox consultée à nouveau. Les états du paiement et de la réparation restent distincts.|A transação Sandbox foi consultada novamente. Os estados do pagamento e da reparação mantêm-se separados.
本地扣款演练已记录；未调用 PayPal，未发生真实或 Sandbox 付款。|Ensayo de cobro local registrado. Sin llamada a PayPal ni pago real o Sandbox.|Essai de débit local consigné. Aucun appel PayPal ni paiement réel ou Sandbox.|Ensaio de cobrança local registado. Sem chamada ao PayPal nem pagamento real ou Sandbox.
本地撤销授权演练已记录；未调用 PayPal。|Ensayo local de anulación registrado. Sin llamada a PayPal.|Essai local d’annulation consigné. Aucun appel PayPal.|Ensaio local de anulação registado. Sem chamada ao PayPal.
Sandbox 授权已核验；款项暂时保留，尚未扣取。|Autorización Sandbox verificada. Fondos retenidos temporalmente; sin cobro.|Autorisation Sandbox vérifiée. Fonds temporairement réservés ; aucun débit.|Autorização Sandbox verificada. Valor retido temporariamente; sem cobrança.
Sandbox 扣款已核验；这不代表真实设备已修复。|Cobro Sandbox verificado. No demuestra que el dispositivo real esté reparado.|Débit Sandbox vérifié. Cela ne prouve pas la réparation du dispositif réel.|Cobrança Sandbox verificada. Não prova que o dispositivo real esteja reparado.
Sandbox 授权已撤销；未执行扣款。|Autorización Sandbox anulada. No hubo cobro.|Autorisation Sandbox annulée. Aucun débit effectué.|Autorização Sandbox anulada. Não houve cobrança.
Sandbox 仍在处理，尚不能确认扣款或授权完成。|Sandbox sigue procesando. No se confirma autorización ni cobro completados.|Sandbox poursuit le traitement. Autorisation ou débit non confirmés.|O Sandbox continua a processar. Autorização ou cobrança ainda não confirmadas.
Sandbox 授权已过期，禁止继续扣款。|Autorización Sandbox vencida. Cobros posteriores bloqueados.|Autorisation Sandbox expirée. Tout nouveau débit est bloqué.|Autorização Sandbox expirada. Novas cobranças bloqueadas.
Sandbox 拒绝本次交易，未记录为成功。|Sandbox rechazó la transacción; no se registra como exitosa.|Sandbox a refusé la transaction ; elle n’est pas enregistrée comme réussie.|O Sandbox recusou a transação; não foi registada como bem-sucedida.
Sandbox 状态已更新。|Estado de Sandbox actualizado.|État Sandbox mis à jour.|Estado Sandbox atualizado.
已检查模拟恢复数据；更换证据后需要重新进行人工复核。|Evidencia de recuperación sintética comprobada. Si cambia, se requiere nueva revisión humana.|Preuves de rétablissement synthétiques contrôlées. Tout changement exige une nouvelle vérification humaine.|Evidência de recuperação sintética verificada. Uma alteração exige nova revisão humana.
''')
PREFIXES = catalogue('''
模拟恢复证据已由人复核，非真实维修：|Evidencia de recuperación sintética revisada por una persona; no es una reparación real: |Preuves synthétiques vérifiées par une personne ; pas une réparation réelle : |Evidência sintética revista por uma pessoa; não é uma reparação real: 
人工复核已记录（模拟现场检查）：|Revisión humana registrada (inspección de campo simulada): |Vérification humaine consignée (inspection sur place simulée) : |Revisão humana registada (inspeção no local simulada): 
模拟复查已记录，非真实维修：|Revisión simulada registrada; no es una reparación real: |Vérification simulée consignée ; pas une réparation réelle : |Revisão simulada registada; não é uma reparação real: 
''')
REPORT = catalogue('''
title|Resumen del caso|Résumé du dossier|Resumo do caso
case|Caso|Dossier|Caso
case_title|Título del caso|Titre du dossier|Título do caso
synthetic|Todas las observaciones e inspecciones de campo son sintéticas o simuladas.|Toutes les observations et inspections sont synthétiques ou simulées.|Todas as observações e inspeções no local são sintéticas ou simuladas.
unknown_data|No consta el origen de los datos. No se afirma validación en campo.|L’origine des données n’est pas consignée. Aucune validation de terrain n’est revendiquée.|A origem dos dados não está registada. Não se afirma validação no terreno.
baseline|El análisis usa una referencia estadística de demostración. Es una pista de inspección, no un diagnóstico físico validado ni inferencia en vivo del modelo de investigación.|L’analyse utilise une référence statistique de démonstration. C’est une piste d’inspection, pas un diagnostic matériel validé ni une inférence en direct du modèle de recherche.|A análise usa uma referência estatística de demonstração. É uma pista de inspeção, não um diagnóstico físico validado nem inferência em direto do modelo de investigação.
separate|El pago no demuestra una reparación. La evidencia de recuperación, la aceptación humana y la transacción se registran por separado.|Le paiement ne prouve pas la réparation. Les preuves de rétablissement, la réception humaine et la transaction sont consignées séparément.|O pagamento não prova uma reparação. A evidência de recuperação, a aceitação humana e a transação são registadas separadamente.
permission|Este informe no autoriza publicar datos de investigación, modelos ni fuentes privadas.|Ce rapport n’autorise pas la publication de données de recherche, de modèles ou de sources privées.|Este relatório não autoriza a publicação de dados de investigação, modelos ou fontes privadas.
redaction|Las notas conservan su idioma. Se omiten rutas locales y valores sensibles; los registros originales no cambian.|Les notes gardent leur langue. Chemins locaux et valeurs sensibles sont masqués ; les originaux restent inchangés.|As notas mantêm o idioma. Caminhos locais e valores sensíveis são omitidos; os registos originais não mudam.
missing|No registrado|Non consigné|Não registado
unknown|Desconocido|Inconnu|Desconhecido
yes|Registrado|Consigné|Registado
no|No registrado|Non consigné|Não registado
overview|Resultado actual|Résultat actuel|Resultado atual
analysis|Evidencia inicial|Éléments initiaux|Evidência inicial
category|Categoría del análisis|Catégorie d’analyse|Categoria da análise
summary|Resumen de evidencia|Résumé des éléments|Resumo da evidência
method|Método de análisis|Méthode d’analyse|Método de análise
decision|Decisión humana|Décision humaine|Decisão humana
note|Nota original de inspección|Note originale d’inspection|Nota original da inspeção
approved|Aprobación del presupuesto|Approbation du devis|Aprovação do orçamento
quote|Presupuesto aprobado|Devis approuvé|Orçamento aprovado
quote_version|Versión del presupuesto|Version du devis|Versão do orçamento
item|Servicio o artículo|Service ou article|Serviço ou artigo
amount|Importe|Montant|Valor
currency|Moneda|Devise|Moeda
seller|Rol del vendedor|Rôle du vendeur|Papel do vendedor
buyer|Rol del comprador|Rôle de l’acheteur|Papel do comprador
quote_at|Fecha de aprobación|Date d’approbation|Data de aprovação
monitoring_service_provider|Proveedor de monitoreo|Prestataire de surveillance|Prestador de monitorização
farm|Granja|Ferme|Quinta
payment|Estado de la transacción|État de la transaction|Estado da transação
mode|Modo de transacción|Mode de transaction|Modo de transação
intent|Tipo de pedido|Type de commande|Tipo de encomenda
order_id|Identificador del pedido|Identifiant de commande|Identificador da encomenda
authorization_id|Identificador de autorización|Identifiant d’autorisation|Identificador da autorização
capture_id|Identificador de cobro|Identifiant du débit|Identificador da cobrança
record_id|Identificador del ensayo local|Identifiant de l’essai local|Identificador do ensaio local
pending|Solicitud sin resolver|Demande non résolue|Pedido por resolver
pending_action|Operación|Opération|Operação
started_at|Inicio de la solicitud|Début de la demande|Início do pedido
local_rehearsal|Ensayo local: sin llamadas a PayPal ni movimiento de fondos|Essai local : aucun appel PayPal ni mouvement de fonds|Ensaio local: sem chamadas ao PayPal nem movimento de fundos
paypal_sandbox|PayPal Sandbox: solo fondos virtuales de prueba|PayPal Sandbox : fonds virtuels de test uniquement|PayPal Sandbox: apenas fundos virtuais de teste
awaiting_buyer|Esperando aprobación del comprador; sin cobro|Approbation de l’acheteur attendue ; aucun débit|A aguardar aprovação do comprador; sem cobrança
authorized|Autorizado; sin cobro|Autorisé ; aucun débit|Autorizado; sem cobrança
completed|Cobro registrado|Débit consigné|Cobrança registada
voided|Autorización anulada; sin cobro|Autorisation annulée ; aucun débit|Autorização anulada; sem cobrança
payment_pending|Resultado del proveedor sin resolver|Résultat du prestataire non résolu|Resultado do prestador por resolver
expired|Autorización vencida|Autorisation expirée|Autorização expirada
denied|Transacción rechazada|Transaction refusée|Transação recusada
legacy_payment|Registro de pago antiguo; no demuestra el proceso actual de reparación antes del cobro.|Ancien paiement ; il ne prouve pas le parcours actuel de réception avant débit.|Pagamento antigo; não prova o processo atual de aceitação antes da cobrança.
recovery|Evidencia de recuperación|Preuves de rétablissement|Evidência de recuperação
source|Fuente de evidencia|Source des éléments|Fonte da evidência
scenario|Escenario de evidencia|Scénario des éléments|Cenário da evidência
samples|Muestras emparejadas válidas|Échantillons appariés valides|Amostras emparelhadas válidas
pass|Comprobaciones de demostración superadas|Contrôles de démonstration réussis|Verificações de demonstração aprovadas
fail|Comprobaciones de demostración fallidas|Contrôles de démonstration échoués|Verificações de demonstração falhadas
insufficient|Evidencia insuficiente|Preuves insuffisantes|Evidência insuficiente
acceptance|Aceptación humana|Réception humaine|Aceitação humana
repair|Estado de reparación o revisión|État de réparation ou de suivi|Estado da reparação ou revisão
unverified|No aceptado o no verificado|Non réceptionné ou non vérifié|Não aceite ou não verificado
verified_demo|Aceptación simulada registrada; sin certificación de reparación real|Réception simulée consignée ; aucune certification de réparation réelle|Aceitação simulada registada; sem certificação de reparação real
acceptance_note|Nota original de aceptación|Note originale de réception|Nota original da aceitação
acceptance_at|Fecha de aceptación|Date de réception|Data de aceitação
warranty_help|La solicitud de garantía es un borrador; la decisión del comerciante y el reembolso no están integrados.|La demande de garantie est un brouillon ; la décision du marchand et le remboursement ne sont pas intégrés.|O pedido de garantia é um rascunho; a decisão do comerciante e o reembolso não estão integrados.
inspect_connection|Revisar conexión compartida|Inspecter la liaison commune|Verificar a ligação comum
replace|Sustitución o servicio fuera de garantía|Remplacement ou service hors garantie|Substituição ou serviço fora da garantia
observe|Seguir observando|Poursuivre l’observation|Continuar a observar
warranty|Borrador de garantía|Brouillon de demande de garantie|Rascunho do pedido de garantia
shared_connection|Indicios de conexión compartida|Indices de liaison commune|Indícios de ligação comum
reading_anomaly|Anomalía de lectura por revisar|Anomalie de mesure à vérifier|Anomalia de leitura a rever
normal|Sin anomalía indicada|Aucune anomalie signalée|Sem anomalia indicada
insufficient_data|Observaciones insuficientes|Observations insuffisantes|Observações insuficientes
checks|Comprobaciones registradas|Contrôles consignés|Verificações registadas
check|Comprobación|Contrôle|Verificação
status|Estado|État|Estado
value|Valor observado|Valeur observée|Valor observado
rule|Comparación requerida|Comparaison requise|Comparação exigida
unit|Unidad|Unité|Unidade
versions|Versiones de evidencia y decisiones|Versions des éléments et décisions|Versões da evidência e decisões
tracked|El seguimiento de versiones empezó con este caso. Solo se muestran actualizaciones registradas.|Le suivi des versions a commencé avec ce dossier. Seules les mises à jour consignées sont listées.|O controlo de versões começou com este caso. Só são apresentadas atualizações registadas.
legacy|Los registros anteriores preceden al seguimiento de versiones. Se desconocen sus fechas originales y versiones previas; no se ha reconstruido el historial.|Les anciens enregistrements précèdent le suivi des versions. Leurs dates initiales et versions antérieures sont inconnues ; aucun historique n’a été reconstitué.|Os registos antigos precedem o controlo de versões. As datas originais e versões anteriores são desconhecidas; o histórico não foi reconstruído.
no_versions|No hay versiones estructuradas de evidencia registradas.|Aucune version structurée des éléments n’est consignée.|Não há versões estruturadas da evidência registadas.
version|Versión|Version|Versão
recorded_at|Fecha de registro|Date de consignation|Data do registo
action|Actualización|Mise à jour|Atualização
review|Revisión humana actualizada|Vérification humaine mise à jour|Revisão humana atualizada
submit_recovery|Evidencia de recuperación actualizada|Preuves de rétablissement mises à jour|Evidência de recuperação atualizada
verify_repair|Aceptación humana registrada|Réception humaine consignée|Aceitação humana registada
before|Antes de esta actualización|Avant cette mise à jour|Antes desta atualização
after|Después de esta actualización|Après cette mise à jour|Após esta atualização
legacy_before|El estado anterior se conservó al hacer esta actualización. Se desconoce su fecha original.|L’état antérieur a été conservé lors de cette mise à jour. Sa date initiale est inconnue.|O estado anterior foi guardado nesta atualização. A data original é desconhecida.
evidence_hash|SHA-256 de evidencia del caso|SHA-256 des éléments du dossier|SHA-256 da evidência do caso
after_hash|SHA-256 del estado actualizado|SHA-256 de l’état mis à jour|SHA-256 do estado atualizado
hash_note|Las sumas de verificación identifican el contenido guardado; no autentican a personas ni certifican reparaciones físicas.|Les empreintes identifient le contenu enregistré ; elles n’authentifient pas une personne et ne certifient pas une réparation physique.|Os resumos identificam o conteúdo guardado; não autenticam pessoas nem certificam reparações físicas.
original|Texto original de la fuente|Texte original de la source|Texto original da fonte
synthetic_fixture|Escenario sintético determinista|Scénario synthétique déterministe|Cenário sintético determinístico
recovered|Ejemplo de recuperación sintética|Exemple de rétablissement synthétique|Exemplo de recuperação sintética
still_faulty|Ejemplo sintético de fallo persistente|Exemple synthétique de panne persistante|Exemplo sintético de avaria persistente
scenario_insufficient|Ejemplo sintético de evidencia incompleta|Exemple synthétique de preuves incomplètes|Exemplo sintético de evidência incompleta
ai|Evidencia de IA|Éléments IA|Evidência de IA
ai_current|Resultado actual de IA|Résultat IA actuel|Resultado atual de IA
ai_bound|Evidencia de IA vinculada a esta revisión humana|Éléments IA liés à cette vérification humaine|Evidência de IA vinculada a esta revisão humana
ai_unbound|Esta decisión humana no tiene evidencia de IA vinculada. Un resultado actual no respalda retroactivamente una decisión anterior.|Aucun élément IA n’a été lié à cette décision humaine. Un résultat actuel ne justifie pas rétroactivement une décision antérieure.|Esta decisão humana não tem evidência de IA vinculada. Um resultado atual não fundamenta retroativamente uma decisão anterior.
ai_boundary|La IA ofrece pistas de inspección. No demuestra la causa de un fallo, no decide garantías, no certifica reparaciones ni autoriza transacciones.|L’IA fournit des pistes d’inspection. Elle n’établit pas la cause d’une panne, ne décide pas des garanties, ne certifie pas les réparations et n’autorise pas les transactions.|A IA fornece pistas de inspeção. Não prova a causa de avarias, não decide garantias, não certifica reparações nem autoriza transações.
ai_ran|Se completó la inferencia local registrada. El modelo se entrenó con datos sintéticos; no es validación de campo ni ejecución en vivo del LSTM de investigación.|L’inférence locale consignée s’est terminée. Le modèle a été entraîné sur des données synthétiques ; ce n’est ni une validation de terrain ni une exécution en direct du LSTM de recherche.|A inferência local registada foi concluída. O modelo foi treinado com dados sintéticos; não é validação no terreno nem execução em direto do LSTM de investigação.
ai_not_ready|No consta un resultado de modelo utilizable. La información ausente no se interpreta como inferencia exitosa.|Aucun résultat de modèle utilisable n’est consigné. Une information absente ne vaut pas inférence réussie.|Não está registado um resultado de modelo utilizável. Informação ausente não equivale a inferência bem-sucedida.
ai_changed|El resultado actual difiere de la revisión guardada. La copia vinculada sigue siendo la evidencia de aquella revisión.|Le résultat actuel diffère de la vérification enregistrée. La copie liée reste la preuve de cette vérification.|O resultado atual difere da revisão guardada. A cópia vinculada continua a ser a evidência dessa revisão.
ai_details|Identificadores del modelo y fuentes originales de las señales|Identifiants du modèle et sources originales des signaux|Identificadores do modelo e fontes originais dos sinais
ai_model|Modelo|Modèle|Modelo
ai_training|Datos de entrenamiento|Données d’entraînement|Dados de treino
ai_synthetic|Solo sintéticos|Synthétiques uniquement|Apenas sintéticos
ai_pattern|Pista de inspección|Piste d’inspection|Pista de inspeção
ai_model_hash|SHA-256 del modelo|SHA-256 du modèle|SHA-256 do modelo
ai_input_hash|SHA-256 de entrada|SHA-256 des entrées|SHA-256 dos dados de entrada
ai_evidence_hash|SHA-256 de evidencia de IA|SHA-256 des éléments IA|SHA-256 da evidência de IA
ai_signal|Señal|Signal|Sinal
ai_device|Identificador original del dispositivo|Identifiant original du dispositif|Identificador original do dispositivo
ai_start|Inicio del intervalo de origen|Début de la fenêtre source|Início do intervalo de origem
ai_end|Fin del intervalo de origen|Fin de la fenêtre source|Fim do intervalo de origem
ai_no_sources|No se registraron intervalos de origen de las señales.|Aucune plage source des signaux n’est consignée.|Não foram registados intervalos de origem dos sinais.
ai_ready|Resultado de inferencia registrado|Résultat d’inférence consigné|Resultado de inferência registado
ai_unavailable|Modelo no disponible|Modèle indisponible|Modelo indisponível
ai_insufficient|Datos de entrada insuficientes|Données d’entrée insuffisantes|Dados de entrada insuficientes
ai_shared_dropout|Varios dispositivos dejaron de enviar datos a la vez; revise su conexión compartida.|Plusieurs dispositifs ont cessé de transmettre ensemble ; inspectez leur liaison commune.|Vários dispositivos deixaram de enviar dados ao mesmo tempo; verifique a ligação comum.
ai_persistent_shift|Un cambio persistente respecto al historial requiere inspección; su causa no está demostrada.|Un écart persistant par rapport à l’historique exige une inspection ; sa cause n’est pas établie.|Uma mudança persistente face ao histórico exige inspeção; a causa não está demonstrada.
ai_stuck|Las lecturas permanecieron inusualmente constantes; revise la sonda y el entorno.|Les mesures sont restées inhabituellement constantes ; vérifiez la sonde et son environnement.|As leituras permaneceram invulgarmente constantes; verifique a sonda e o ambiente.
ai_normal|Ningún patrón de anomalía probado destacó.|Aucun schéma d’anomalie testé ne s’est distingué.|Nenhum padrão de anomalia testado se destacou.
ai_single_dropout|Un dispositivo dejó de enviar datos; revise la conexión y la alimentación.|Un dispositif a cessé de transmettre ; vérifiez la connexion et l’alimentation.|Um dispositivo deixou de enviar dados; verifique a ligação e a alimentação.
ai_dropout|Los vacíos de datos requieren investigación; se desconoce la causa.|Les interruptions de transmission nécessitent une enquête ; la cause est inconnue.|As falhas de envio exigem investigação; a causa é desconhecida.
ai_disagreement|Las fuentes de evidencia discrepan; se requiere más inspección humana.|Les sources divergent ; une inspection humaine supplémentaire est nécessaire.|As fontes de evidência discordam; é necessária mais inspeção humana.
calibration_points|Observaciones de calibración|Observations de calibration|Observações de calibração
detection_observed_points|Observaciones válidas de detección|Observations valides de détection|Observações válidas de deteção
median_residual_vwc|Diferencia mediana respecto a la referencia|Écart médian à la référence|Diferença mediana face à referência
flat_duration_hours|Duración sin cambios de lectura|Durée des mesures constantes|Duração das leituras constantes
trailing_missing_hours|Vacío de datos al final|Lacune de transmission finale|Falha de dados no fim
historical_noise_vwc|Variación histórica de lecturas|Variation historique des mesures|Variação histórica das leituras
count|observaciones|observations|observações
percentage_points|puntos porcentuales|points de pourcentage|pontos percentuais
hours|horas|heures|horas
observation_window|Duración de observación|Durée d’observation|Duração da observação
paired_samples|Muestras emparejadas|Échantillons appariés|Amostras emparelhadas
link_samples|Observaciones de conexión|Observations de connexion|Observações de ligação
link_success_ratio|Proporción de conexiones correctas|Proportion de connexions réussies|Proporção de ligações bem-sucedidas
reference_variation|Variación de la referencia|Variation de la référence|Variação da referência
mean_absolute_error|Error absoluto medio|Erreur absolue moyenne|Erro absoluto médio
max_absolute_error|Error absoluto máximo|Erreur absolue maximale|Erro absoluto máximo
sensor_variation|Variación de la sonda|Variation de la sonde|Variação da sonda
create_order|Crear pedido de autorización|Créer la commande d’autorisation|Criar encomenda de autorização
authorize|Verificar autorización|Vérifier l’autorisation|Verificar autorização
capture|Cobrar importe aprobado|Débiter le montant approuvé|Cobrar o valor aprovado
void|Anular autorización|Annuler l’autorisation|Anular autorização
reconcile|Consultar transacción|Vérifier la transaction|Consultar transação
redacted|[omitido]|[masqué]|[omitido]
path_omitted|[ruta local omitida]|[chemin local masqué]|[caminho local omitido]
''')
REPORT.update(catalogue("""
hourly_window|ventana horaria|fenêtre horaire|janela horária
ratio|proporción|proportion|proporção
sample_unit|muestras|échantillons|amostras
true|Sí|Oui|Sim
false|No|Non|Não
"""))
