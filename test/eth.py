import json


def build_operation(path, value):
    return {
        "op": "add",
        "path": f"/fields/{path}",
        "value": value
    }


def prepare_patch(wi_settings):
    patch = []
    for key, value in wi_settings['/fields/'].items():
        patch.append(build_operation(key, value))

    if wi_settings["ParentWorkItemId"] != "":
        patch.append({
            "op": "add",
            "path": "/relations/-",
            "value":
                {
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": f"http://ztfs-2017:8080/tfs/Fintech/_apis/wit/workItems/{wi_settings['ParentWorkItemId']}",
                }
        })
    return patch


settings = {
    "ФЦОД-М": {
        "ParentWorkItemId": "42406",
        "/fields/": {
            "System.AssignedTo": "Карпов Егор Михайлович <FINTECH\\karpov>",
            "System.Tags": ["tg-support"],
            "System.IterationPath": "Mir\\999-Future",
            "System.AreaPath": "Mir\\ФЦОД-М",
            "Microsoft.VSTS.Common.Severity": "2 - High",
        }
    }
}

s = settings["ФЦОД-М"]
print(prepare_patch(s))



def a():
    j = json.dumps(settings, indent=4, ensure_ascii=False)
    with open("../tfs_bot/settings.json", "w") as outfile:
        outfile.write(j)

    with open('../tfs_bot/settings.json', 'r') as openfile:
        # Reading from json file
        json_object = json.load(openfile)

    print(json_object)

