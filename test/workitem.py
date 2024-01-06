import json

import requests
import requests_kerberos


def prepare_defect(title, descr, info):
    base_uri = 'http://ztfs-2017:8080/tfs/Fintech/MIR/'
    projects_api = '_apis/wit/workitems/$bug' + "?api-version=4.0-preview"

    patch = [
        {
            "op": "add",
            "path": "/fields/System.Tags",
            "value": "tg-support"
        },
        {
            "op": "add",
            "path": "/fields/System.AreaPath",
            "value": "Mir\\ФЦОД-М"
        },
        {
            "op": "add",
            "path": "/fields/System.title",
            "value": title
        },
        {
            "op": "add",
            "path": "/fields/Microsoft.VSTS.TCM.ReproSteps",
            "value": descr
        },
        {
            "op": "add",
            "path": "/fields/Microsoft.VSTS.TCM.SystemInfo",
            "value": info
        },

    ]

    resp = requests.post(base_uri + projects_api,
                         headers={'Content-Type': 'application/json-patch+json'}, json=patch,
                         auth=requests_kerberos.HTTPKerberosAuth())

    j = json.loads(prepare_defect("Test", "some descr", "Created from script").content)

    return json.loads(resp.content)["id"]


def query_wi() -> str:
    instance = 'ztfs-2017:8080/tfs'
    collection = 'Fintech'
    project = 'MIR'
    team = 'FCOD-M'
    id = 'f33d826e-59cf-4c2c-b6c5-e0a761f29dfa'
    uri = f'http://{instance}/{collection}/{project}/{team}/_apis/wit/wiql/{id}?api-version=4.1'

    # запрос возвращает коллекцию идентификаторов в блоке workItems
    # http://ztfs-2017:8080/tfs/Fintech/MIR/FCOD-M/_apis/wit/wiql/f33d826e-59cf-4c2c-b6c5-e0a761f29dfa?api-version=4.1
    resp = requests.get(uri,
                         headers={'Content-Type': 'application/json-patch+json'},
                         auth=requests_kerberos.HTTPKerberosAuth())

    j = json.loads(resp.content)
    output_srting = f'{str.ljust("Id", 7)}| {str.ljust("State", 10)}| Title\r\n'

    # перемещаемся по прямым ссылкам WI и сразу извлекаем секцию fields, собираем строку выдачи
    for items in j['workItems']:
        fields = json.loads(requests.get(items['url'],
                            headers={'Content-Type': 'application/json-patch+json'},
                            auth=requests_kerberos.HTTPKerberosAuth()).content)['fields']
        id = str(items['id'])
        state = fields['System.State']
        title = fields['System.Title']
        output_srting += f"{str.ljust(id,7)}| {str.ljust(state,10)}| {title}\r\n"
    return output_srting


def parse_message(message:str):
    kwrds = {'ошибка', 'ошибку', 'ошибки', 'проблема', 'проблемы', 'проблему', 'дефект'}
    sp = message.lower().split()
    r = kwrds.intersection(sp)
    if (len(r) > 0):
        return True
    return False

print(parse_message('На заборе висела Ошибка'))



