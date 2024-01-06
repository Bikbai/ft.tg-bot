import json
from array import array

import requests
import requests_kerberos


class Patch:

    def __init__(self, settings, project_string):
        """ Создаёт сразу патч с нужными полями """
        self.__patch = []
        self.__project_settings = {}

        # грузим настройки сопоставления workitem
        for value in settings:
            if value["project_code"] == project_string:
                self.__project_settings = value
                break

        # проверяем, что такой проект есть в настройках
        if not self.__project_settings:
            raise ValueError(f"Не найдены настройки проекта {project_string}")

        for key, value in self.__project_settings['/fields/'].items():
            self.__patch.append(self.__build_operation(key, value))

        if self.__project_settings["ParentWorkItemId"] != "":
            self.__patch.append({
                "op": "add",
                "path": "/relations/-",
                "value":
                    {
                        "rel": "System.LinkTypes.Hierarchy-Reverse",
                        "url": f"http://ztfs-2017:8080/tfs/Fintech/_apis/wit/workItems/"
                               f"{self.__project_settings['ParentWorkItemId']}",
                    }
            })

    @staticmethod
    def __build_operation(path, value):
        return {
            "op": "add",
            "path": f"/fields/{path}",
            "value": value
        }

    def __merge_operation(self, operation):
        if operation['path'] == '/fields/System.Tags':
            for value in self.__patch:
                if value['path'] == operation['path']:
                    value['value'] = f"{value['value']},{operation['value']}"
                    return
        self.__patch.append(operation)
        return

    def get(self):
        return self.__patch

    def add(self, key, value):
        op = self.__build_operation(key, value)
        self.__merge_operation(operation=op)


class TfsManipulator:

    def __init__(self):
        with open('settings.json', 'r') as openfile:
            # Reading from json file
            json_settings = json.load(openfile)

        self.instance = json_settings["instance"]
        self.collection = json_settings["collection"]
        self.project = json_settings["tfs_project"]
        self.team = json_settings["team"]
        self.query_id = json_settings["query_id"]

        """ СПИСОК настроек WI для проекта """
        self.settings = json_settings["projects"]

    def create_wi(self, project_string, title: str, descr: str, info: str, request_number: str = "") -> int:
        """ Метод создаёт WI в TFS и возвращает его номер. В случае ошибки возвращает -1"""

        uri = f'http://{self.instance}/{self.collection}/{self.project}/_apis/wit/workitems/$bug?api-version=4.0-preview'

        patch = Patch(project_string=project_string, settings=self.settings)

        if request_number != "":
            title = f'{request_number}. {title}'
            patch.add(key="System.Tags", value="АСУ")

        patch.add("System.title", title)
        patch.add("Microsoft.VSTS.TCM.ReproSteps", descr)
        patch.add("Microsoft.VSTS.TCM.SystemInfo", info)

        resp = requests.post(uri,
                             headers={'Content-Type': 'application/json-patch+json'},
                             json=patch.get(),
                             auth=requests_kerberos.HTTPKerberosAuth())
        if resp.status_code != 200:
            return -1
        return json.loads(resp.content)["id"]

    def query_wi(self) -> str:
        """ Метод выполняет QUERY в TFS и возвращает его в виде форматированной строки для вывода """
        uri = f'http://{self.instance}/{self.collection}/{self.project}/{self.team}/_apis/wit/wiql/{self.query_id}?api-version=4.1'

        # запрос возвращает коллекцию идентификаторов в блоке workItems
        # это грязный хак, такой запрос должен быть в TFS
        # http://ztfs-2017:8080/tfs/Fintech/MIR/FCOD-M/_apis/wit/wiql/f33d826e-59cf-4c2c-b6c5-e0a761f29dfa?api-version=4.1
        resp = requests.get(uri,
                            headers={'Content-Type': 'application/json-patch+json'},
                            auth=requests_kerberos.HTTPKerberosAuth())

        j = json.loads(resp.content)
        if len(j['workItems']) == 0:
            return 'Активных заявок нет'

        output_string = f"Найдено заявок: {len(j['workItems'])}\r\n"
        output_string += '---------------\r\n'

        output_string += f'{str.ljust("Id", 7)}| {str.ljust("State", 10)}| Title\r\n'

        # перемещаемся по прямым ссылкам WI и сразу извлекаем секцию fields, собираем строку выдачи
        for items in j['workItems']:
            fields = json.loads(requests.get(f"{items['url']}?fields=System.State,System.Title",
                                             headers={'Content-Type': 'application/json-patch+json'},
                                             auth=requests_kerberos.HTTPKerberosAuth()).content)['fields']
            id = str(items['id'])
            state = fields['System.State']
            if len(fields['System.Title']) > 30:
                title = fields['System.Title'][0:28] + '..'
            else:
                title = fields['System.Title']
            output_string += f"{str.ljust(id, 7)}| {str.ljust(state, 10)}| {title}\r\n"
        output_string = f"```\n{output_string}```\n"
        return output_string

    def make_wi_attach(self, workitem_id: int, data: bytes, filename: str):
        uri = f'http://{self.instance}/{self.collection}/{self.project}/_apis/wit/attachments?api-version=4.1'
        resp = requests.post(uri,
                          data=data,
                          headers={
                              "Accept": "application/json",
                              'Content-Type': 'application/octet-stream',
                              "Content-Size": str(len(data)),
                          },
                          auth=requests_kerberos.HTTPKerberosAuth())

        if resp.status_code != 200:
            return resp.status_code

        patch = [
            {
                "op": "add",
                "path": "/relations/-",
                "value":
                    {
                        "rel": "AttachedFile",
                        "url": f"{resp_json['url']}?fileName={filename}"
                    }
            }, ]

        uri = f'http://{self.instance}/{self.collection}/_apis/wit/workitems/{workitem_id}?' \
              f'api-version=4.1&fields=System.State'

        resp = requests.patch(uri,
                              json=patch,
                              headers={'Content-Type': 'application/json-patch+json'},
                              auth=requests_kerberos.HTTPKerberosAuth())

        return resp.status_code



    def check_wi_exists(self, workitem_id: int) -> bool:
        get_uri = f'http://{self.instance}/{self.collection}/{self.project}/_apis/wit/workitems/{workitem_id}?api-version=4.1'
        resp = requests.get(get_uri, auth=requests_kerberos.HTTPKerberosAuth())
        if resp.status_code == 200:
            # wi_data = json.loads(resp.content)
            return True
        return False

# print(check_wi_exists(43206))
