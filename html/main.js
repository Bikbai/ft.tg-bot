Telegram.WebApp.ready();
Telegram.WebApp.expand();
document.getElementById('tfs_title').focus();
document.getElementById('status').innerText = "Загружен успешно";
Telegram.WebApp.MainButton.setText('Сохранить и закрыть').show().onClick(function () {
    let data = {
        "title": document.querySelector('#tfs_title').value,
        "descr": document.querySelector('#tfs_description').value,
        "project": document.querySelector('#project').value,
        "request_number":document.querySelector('#request_number').value};
    Telegram.WebApp.sendData(JSON.stringify(data));
    Telegram.WebApp.close();
});