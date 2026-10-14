"""El kit de NICS separa los 3 servicios del banco de pruebas y respeta el alcance autorizado."""

import pandas as pd
import pytest

from kits.nics import classifier, collector, features, inventory, testbed


def test_alcance_por_defecto_solo_localhost():
    t = pd.DataFrame({"name": ["x"], "url": ["http://8.8.8.8:80"]})
    with pytest.raises(SystemExit):
        inventory.check_scope(t, None)
    inventory.check_scope(t, ["8.8.8.0/24"])  # autorizado explícitamente: no aborta


def test_inventario_host_port(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("host,port\n10.0.0.5,8080\n10.0.0.6,443\n", encoding="utf-8")
    t = inventory.load_targets(p)
    assert t["url"].tolist() == ["http://10.0.0.5:8080", "https://10.0.0.6:443"]


def test_inventario_desde_txt_xml_y_gnmap(tmp_path):
    txt = tmp_path / "s.txt"
    txt.write_text("# comentario\n10.0.0.5:8080\n\nhttps://10.0.0.6:9443/app\n10.0.0.7:443\n", encoding="utf-8")
    assert inventory.load_targets(txt)["url"].tolist() == ["http://10.0.0.5:8080", "https://10.0.0.6:9443/app", "https://10.0.0.7:443"]

    xml = tmp_path / "r.xml"
    xml.write_text('<nmaprun><host><address addr="10.0.0.5" addrtype="ipv4"/><ports>'
                   '<port portid="80"><state state="open"/><service name="http"/></port>'
                   '<port portid="22"><state state="open"/><service name="ssh"/></port>'
                   '<port portid="8443"><state state="open"/><service name="http" tunnel="ssl"/></port>'
                   '<port portid="81"><state state="closed"/><service name="http"/></port>'
                   '</ports></host></nmaprun>', encoding="utf-8")
    assert inventory.load_targets(xml)["url"].tolist() == ["http://10.0.0.5:80", "https://10.0.0.5:8443"]

    gn = tmp_path / "r.gnmap"
    gn.write_text("Host: 10.0.0.9 ()\tPorts: 80/open/tcp//http///, 22/open/tcp//ssh///, 443/open/tcp//https///\n", encoding="utf-8")
    assert inventory.load_targets(gn)["url"].tolist() == ["http://10.0.0.9:80", "https://10.0.0.9:443"]


def test_banco_de_pruebas_3_de_3(monkeypatch):
    monkeypatch.setattr(testbed, "_ollama_ok", False)  # simulador: rápido y sin depender de Ollama
    servers = testbed.start()
    try:
        targets = inventory.load_targets(testbed.__file__.replace("testbed.py", "targets_testbed.csv"))
        cfg = collector.load_probes()
        ev = collector.collect(targets, cfg | {"pausa_ms": 0}, repeats=3)
    finally:
        testbed.stop(servers)
    rules = classifier.load_rules()
    res = classifier.classify(features.service_features(ev, rules), rules)
    got = dict(zip(res["url_base"], res["clase"]))
    assert got == dict(zip(targets["url"], targets["etiqueta_real"]))
