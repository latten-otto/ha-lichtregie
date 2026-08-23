/**
 * Lichtregie — eigenständige Oberfläche.
 *
 * Läuft als Panel in der Seitenleiste und benutzt die bereits angemeldete
 * WebSocket-Verbindung des Frontends. Bewusst ohne Build-Kette und ohne
 * fremde Bibliotheken: ein Modul, das der Browser direkt lädt.
 */

const CSS = `
:host{
  --bg:#0E0F12; --panel:#16181D; --panel2:#1D2027; --line:#282C35;
  --ink:#E8E9EC; --soft:#9AA0AC; --faint:#646A78;
  --amber:#F0A63C; --blue:#5FA8D8; --green:#69B87C; --red:#E0705C; --violet:#9B84D4;
  display:block; min-height:100%; background:var(--bg); color:var(--ink);
  font-family:"Archivo",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  font-size:14px;
}
*{box-sizing:border-box}
button{font:inherit;color:inherit;background:none;border:0;cursor:pointer}
.top{display:flex;align-items:center;gap:14px;padding:10px 18px;background:#101216;
  border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
.brand{font-weight:700;letter-spacing:.02em;color:var(--amber);display:flex;align-items:center;gap:8px}
.brand i{width:10px;height:10px;border-radius:2px;background:linear-gradient(135deg,#FFB84D,#E07B2C)}
.crumb{font-family:ui-monospace,monospace;font-size:12px;color:var(--faint)}
.top .right{margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.chip{font-family:ui-monospace,monospace;font-size:11px;padding:3px 8px;border-radius:4px;
  border:1px solid var(--line);color:var(--soft);background:var(--panel)}
.chip.ok{color:var(--green);border-color:#2A4433}
.chip.warn{color:var(--amber);border-color:#4A3B22}
.chip.alarm{color:var(--red);border-color:#4A2A26}
.body{display:grid;grid-template-columns:172px 1fr;min-height:calc(100vh - 44px)}
nav{border-right:1px solid var(--line);padding:12px 0;background:#121419}
nav button{display:block;width:100%;text-align:left;padding:8px 18px;font-size:13px;
  color:var(--soft);border-left:2px solid transparent}
nav button.on{color:var(--ink);border-left-color:var(--amber);background:#191C22}
nav .grp{font-size:10px;text-transform:uppercase;letter-spacing:.12em;color:var(--faint);padding:16px 18px 6px}
main{padding:20px 22px;min-width:0;overflow-x:hidden}
h2{font-size:17px;font-weight:600;margin:0 0 3px}
.sub{font-size:12.5px;color:var(--faint);margin:0 0 18px}
.sec{font-size:10.5px;text-transform:uppercase;letter-spacing:.13em;color:var(--faint);
  margin:24px 0 10px;display:flex;align-items:center;gap:10px}
.sec::after{content:"";flex:1;height:1px;background:var(--line)}
.zones{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px}
.zt{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:13px 14px;
  text-align:left;position:relative;width:100%}
.zt:hover{border-color:#3A404C}
.zt.act{border-color:#4A3B22}
.zt.fault{border-color:#4A2A26}
.zname{font-size:14px;font-weight:600;margin-bottom:3px}
.zstate{font-size:11px;color:var(--faint);font-family:ui-monospace,monospace}
.lvl{position:absolute;top:12px;right:14px;font-family:ui-monospace,monospace;font-size:12px;color:var(--amber)}
.lvl.off{color:var(--faint)}
.bar{height:3px;border-radius:2px;background:var(--line);margin-top:10px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--amber)}
.row{display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin-top:16px}
.btn{padding:7px 14px;border-radius:6px;border:1px solid var(--line);color:var(--soft);
  background:var(--panel);font-size:13px}
.btn:hover{color:var(--ink);border-color:#3A404C}
.btn.pri{background:var(--amber);border-color:var(--amber);color:#231603;font-weight:600}
.btn.on{background:var(--panel2);color:var(--amber);border-color:#4A3B22}
.faders{display:flex;gap:12px;overflow-x:auto;padding:8px 2px}
.fader{width:72px;flex:0 0 72px;display:flex;flex-direction:column;align-items:center;gap:8px}
.fname{font-size:11px;color:var(--soft);text-align:center;line-height:1.3;height:28px;overflow:hidden}
.fader input[type=range]{writing-mode:vertical-lr;direction:rtl;width:30px;height:130px;accent-color:var(--amber)}
.fval{font-family:ui-monospace,monospace;font-size:12px}
.role{font-size:9.5px;letter-spacing:.06em;text-transform:uppercase;padding:2px 5px;border-radius:3px;
  border:1px solid var(--line);color:var(--faint)}
.role.general{color:#B9BFCB}.role.task{color:var(--blue);border-color:#27455A}
.role.ambient{color:var(--amber);border-color:#4A3B22}.role.accent{color:var(--violet);border-color:#3B3358}
.role.night{color:#8FA5C9;border-color:#2A3448}
.stack{display:flex;flex-direction:column;gap:5px}
.layer{display:grid;grid-template-columns:30px 1fr auto auto;gap:12px;align-items:center;
  padding:9px 12px;border-radius:7px;border:1px solid var(--line);background:var(--panel);font-size:13px}
.layer.dim{opacity:.4}
.layer.act{border-color:var(--amber);background:#221A0F}
.layer .p{font-family:ui-monospace,monospace;font-size:11px;color:var(--faint)}
.layer.act .p{color:var(--amber)}
.layer .src{font-size:11px;color:var(--faint)}
.layer .ttl{font-family:ui-monospace,monospace;font-size:11px;color:var(--soft)}
.slist{display:flex;flex-direction:column;gap:4px}
.srow{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:6px;font-size:13px;
  border:1px solid transparent;color:var(--soft);text-align:left;width:100%}
.srow:hover{background:var(--panel)}
.srow.on{background:var(--panel2);border-color:#4A3B22;color:var(--ink)}
.srow .dot{width:7px;height:7px;border-radius:50%;background:var(--line);flex:0 0 auto}
.srow.on .dot{background:var(--amber)}
.srow .meta{margin-left:auto;font-family:ui-monospace,monospace;font-size:11px;color:var(--faint)}
.srow .del{width:24px;color:var(--faint);font-size:15px;padding:0}
.srow .del:hover{color:var(--red)}
.btn[disabled]{opacity:.45;cursor:default}
.btn[disabled]:hover{color:var(--soft);border-color:var(--line)}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--faint);
  font-weight:600;padding:9px 12px;border-bottom:1px solid var(--line)}
td{padding:9px 12px;border-bottom:1px solid #1F2229;color:var(--soft);vertical-align:top}
td b{color:var(--ink);font-weight:600}
.mono{font-family:ui-monospace,monospace;font-size:11px;color:var(--faint)}
.tl{display:grid;grid-template-columns:72px 1fr;gap:0 14px}
.tl .t{font-family:ui-monospace,monospace;font-size:11px;color:var(--faint);padding:9px 0;text-align:right}
.tl .c{padding:9px 0 10px;border-left:1px solid var(--line);padding-left:16px;position:relative}
.tl .c::before{content:"";position:absolute;left:-4px;top:13px;width:7px;height:7px;border-radius:50%;
  background:var(--panel);border:1.5px solid var(--faint)}
.tl .c.hot::before{border-color:var(--amber)}
.tl .c.bad::before{border-color:var(--red)}
.tl .c b{display:block;font-size:12.5px}
.tl .c span{font-size:11.5px;color:var(--faint)}
.empty{color:var(--faint);font-size:13px;padding:30px 0;text-align:center}
.learn{margin-top:12px;padding:10px 13px;border:1px dashed #3A404C;border-radius:7px;
  font-size:12px;color:var(--faint)}
.learn b{color:var(--amber)}
select,input[type=text],input[type=number]{background:var(--panel);border:1px solid var(--line);
  color:var(--ink);border-radius:6px;padding:6px 9px;font:inherit;font-size:12.5px}
select:focus,input:focus{outline:1px solid var(--amber);outline-offset:1px}
.bind{display:grid;grid-template-columns:92px 104px minmax(210px,1fr) minmax(215px,250px) 100px 30px;gap:8px;align-items:center;
  padding:8px 10px;border-radius:7px;border:1px solid var(--line);background:var(--panel);margin-bottom:5px}
.bind .del{color:var(--faint);font-size:16px;text-align:center;padding:0}
.bind .del:hover{color:var(--red)}
.bind.head{background:#12141A;border-color:#12141A;font-size:10px;text-transform:uppercase;
  letter-spacing:.1em;color:var(--faint)}
.tmpl{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px;margin-top:10px}
.tcard{border:1px solid var(--line);border-radius:8px;padding:11px 13px;background:var(--panel);text-align:left}
.tcard:hover{border-color:var(--amber)}
.tcard b{display:block;font-size:13px;margin-bottom:3px}
.tcard span{font-size:11.5px;color:var(--faint);line-height:1.45}
.toggle{display:flex;align-items:center;gap:9px;font-size:13px;padding:8px 12px;border-radius:7px;
  border:1px solid var(--line);background:var(--panel)}
.toggle i{width:30px;height:16px;border-radius:9px;background:var(--line);position:relative;flex:0 0 auto}
.toggle i::after{content:"";position:absolute;top:2px;left:2px;width:12px;height:12px;border-radius:50%;
  background:var(--faint);transition:.15s}
.toggle.on i{background:#4A3B22}
.toggle.on i::after{left:16px;background:var(--amber)}
.curvebox{border:1px solid var(--line);border-radius:9px;background:var(--panel);padding:12px}
.lamp{display:grid;grid-template-columns:minmax(190px,2fr) 128px 96px 104px 104px 92px;gap:8px;
  align-items:center;padding:9px 11px;border-radius:7px;border:1px solid var(--line);
  background:var(--panel);margin-bottom:5px}
.lamp.head{background:#12141A;border-color:#12141A;font-size:10px;text-transform:uppercase;
  letter-spacing:.1em;color:var(--faint);padding:7px 11px}
.lamp.off{opacity:.5}
.lamp[data-lampdlg]{cursor:pointer}
.lamp[data-lampdlg]:hover{border-color:#3A404C;background:var(--panel2)}
.lamp[data-lampdlg]:hover .nam{text-decoration:underline;text-underline-offset:2px}
.lamp .nam{font-weight:600}
/* Bedienelemente in der Zeile öffnen den Dialog nicht. */
.lamp select,.lamp input,.lamp .toggle{cursor:auto}
.lamp .lname{font-size:13px;font-weight:600}
.lamp .lent{font-family:ui-monospace,monospace;font-size:10.5px;color:var(--faint)}
.lamp .num{display:flex;align-items:center;gap:5px}
.lamp .num input{width:56px;text-align:right}
.lamp .unit{font-family:ui-monospace,monospace;font-size:11px;color:var(--faint)}
.lamp .kann{font-size:11px;color:var(--faint)}
.zonebar{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:6px}
.overlay{position:fixed;inset:0;background:rgba(6,7,9,.72);display:flex;align-items:center;
  justify-content:center;z-index:50;padding:20px}
.dialog{background:var(--panel);border:1px solid var(--line);border-radius:12px;width:min(560px,100%);
  max-height:88vh;overflow:auto;box-shadow:0 24px 60px rgba(0,0,0,.6)}
.dialog header{display:flex;align-items:center;gap:12px;padding:16px 20px;border-bottom:1px solid var(--line)}
.dialog header .ic{width:38px;height:38px;border-radius:9px;background:var(--panel2);
  display:flex;align-items:center;justify-content:center;font-size:19px;flex:0 0 auto}
.dialog header h3{margin:0;font-size:15px;font-weight:600}
.dialog header .ent{font-family:ui-monospace,monospace;font-size:11px;color:var(--faint)}
.dialog header .x{margin-left:auto;font-size:20px;color:var(--faint);padding:0 4px}
.dialog header .x:hover{color:var(--ink)}
.dialog .dlgbody{padding:18px 20px}
.dialog footer{display:flex;gap:9px;padding:14px 20px;border-top:1px solid var(--line);align-items:center}
.dialog footer .weg{margin-left:auto;color:var(--red);border-color:#4A2A26}
.feld{margin-bottom:16px}
.feld label{display:block;font-size:10.5px;text-transform:uppercase;letter-spacing:.1em;
  color:var(--faint);margin-bottom:6px}
.feld input[type=text],.feld select{width:100%}
.feld .zeile{display:flex;gap:9px;align-items:center}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chipbtn{padding:6px 12px;border-radius:100px;border:1px solid var(--line);font-size:12.5px;
  color:var(--soft);background:var(--panel2)}
.chipbtn.on{border-color:var(--amber);color:var(--amber);background:#221A0F}
.chipbtn.haupt::after{content:" · Haupt";font-size:10px;opacity:.8}
.iconwahl{display:flex;gap:6px;flex-wrap:wrap}
.iconbtn{width:36px;height:36px;border-radius:8px;border:1px solid var(--line);background:var(--panel2);
  font-size:17px;display:flex;align-items:center;justify-content:center}
.iconbtn.on{border-color:var(--amber);background:#221A0F}
.lamp .sym{font-size:16px;margin-right:8px}
.lamp .rollen{font-size:10px;color:var(--faint);letter-spacing:.03em}
.rule{display:grid;grid-template-columns:minmax(150px,1.2fr) minmax(140px,1fr) 120px 130px 30px;
  gap:8px;align-items:center;padding:8px 11px;border-radius:7px;border:1px solid var(--line);
  background:var(--panel);margin-bottom:5px}
.rule.head{background:#12141A;border-color:#12141A;font-size:10px;text-transform:uppercase;
  letter-spacing:.1em;color:var(--faint)}
.rule .src{font-size:12.5px}
.rule .ent{font-family:ui-monospace,monospace;font-size:10.5px;color:var(--faint)}
.hint{font-size:12px;color:var(--faint);margin:6px 0 0;line-height:1.5}
@media(max-width:980px){
  .lamp{grid-template-columns:minmax(150px,1.4fr) 120px 92px 96px;}
  .lamp > :nth-child(n+5){display:none}
}
@media(max-width:700px){
  .lamp{grid-template-columns:1fr 1fr}
  .rule{grid-template-columns:1fr 1fr}
  .bind{grid-template-columns:1fr 1fr;}
  .bind.head{display:none}
  .body{grid-template-columns:1fr}
  nav{display:flex;overflow-x:auto;border-right:0;border-bottom:1px solid var(--line);padding:6px 4px}
  nav .grp{display:none}
  nav button{width:auto;white-space:nowrap;border-left:0;border-bottom:2px solid transparent;padding:7px 13px}
  nav button.on{border-left:0;border-bottom-color:var(--amber)}
}
`;

const ROLE_ICONS = ["💡", "🔆", "🛋", "🕯", "🌙", "🎨", "🔦", "🖼", "🪞", "🍽", "🛏", "🚿"];

const ROLE_DEFAULT_ICON = {
  general: "💡",
  task: "🔆",
  ambient: "🛋",
  accent: "🕯",
  night: "🌙",
  effect: "🎨",
};

const ROLE_LABEL = {
  general: "Grund",
  task: "Arbeit",
  ambient: "Stimm",
  accent: "Akzent",
  night: "Nacht",
  effect: "Effekt",
};

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

const secs = (v) => {
  if (v === null || v === undefined) return "";
  if (v > 3600) return `${Math.floor(v / 3600)}:${String(Math.floor((v % 3600) / 60)).padStart(2, "0")} h`;
  if (v > 90) return `${Math.round(v / 60)} min`;
  return `${Math.round(v)} s`;
};

const clock = (t) => new Date(t * 1000).toLocaleTimeString("de-DE");

class LichtregiePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._view = "leitstand";
    this._zoneId = null;
    this._config = null;
    this._state = null;
    this._journal = [];
    this._lastGesture = null;
    this._controlId = null;
    this._templates = [];
    this._curves = null;
    this._editScene = null;
    this._dirty = false;
    this._draft = {};
    this._dialog = null;
    this._freeLights = null;
    this._showOverrides = false;
    this._busy = "";
    this._bound = false;
    this._ready = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._ready) {
      this._ready = true;
      this._boot();
    }
  }

  async _call(type, extra = {}) {
    return this._hass.connection.sendMessagePromise({ type, ...extra });
  }

  async _boot() {
    this.shadowRoot.innerHTML = `<style>${CSS}</style><div id="app"></div>`;
    try {
      this._config = await this._call("lichtregie/config/get");
      this._state = await this._call("lichtregie/state");
      const answer = await this._call("lichtregie/journal", { limit: 120 });
      this._journal = answer.eintraege || [];
      const templates = await this._call("lichtregie/templates");
      this._templates = templates.vorlagen || [];
    } catch (err) {
      this._error = String(err && err.message ? err.message : err);
    }
    this._subscribe();
    this._render();
  }

  async _subscribe() {
    try {
      this._unsub = await this._hass.connection.subscribeMessage(
        (msg) => this._onPush(msg),
        { type: "lichtregie/subscribe" }
      );
    } catch (err) {
      /* Ohne Live-Zustand bleibt die Oberfläche bedienbar. */
    }
  }

  disconnectedCallback() {
    if (this._unsub) this._unsub();
  }

  _onPush(msg) {
    if (!msg) return;
    if (msg.art === "zone" && this._state) {
      const index = this._state.zones.findIndex((z) => z.id === msg.daten.id);
      if (index >= 0) this._state.zones[index] = msg.daten;
      else this._state.zones.push(msg.daten);
      this._render();
    } else if (msg.art === "protokoll") {
      this._journal.unshift(msg.daten);
      this._journal = this._journal.slice(0, 200);
      if (this._view === "protokoll") this._render();
    } else if (msg.art === "gesture") {
      this._lastGesture = { ...msg.daten, at: Date.now() };
      if (this._view === "bedienung") this._render();
    }
  }

  // -- Hilfen ---------------------------------------------------------------

  get zones() {
    return (this._config && this._config.zones) || [];
  }

  get controls() {
    return (this._config && this._config.controls) || [];
  }

  zoneState(id) {
    return ((this._state && this._state.zones) || []).find((z) => z.id === id) || {};
  }

  zoneConfig(id) {
    return this.zones.find((z) => z.id === id) || null;
  }

  // -- Rendern --------------------------------------------------------------

  _render() {
    const app = this.shadowRoot.getElementById("app");
    if (!app) return;

    const faults = (this._state && this._state.stats && this._state.stats.faults) || [];
    const lit = ((this._state && this._state.zones) || []).filter((z) => z.master > 0);

    app.innerHTML = `
      <div class="top">
        <span class="brand"><i></i>Lichtregie</span>
        <span class="crumb">${esc(this._crumb())}</span>
        <span class="right">
          <span class="chip">${this.zones.length} Zonen</span>
          <span class="chip ${lit.length ? "warn" : "ok"}">${lit.length} beleuchtet</span>
          ${faults.length ? `<span class="chip alarm">${faults.length} Störung</span>` : ""}
        </span>
      </div>
      <div class="body">
        <nav>
          <div class="grp">Betrieb</div>
          ${this._navButton("leitstand", "Leitstand")}
          <div class="grp">Einrichtung</div>
          ${this._navButton("lampen", "Lampen")}
          ${this._navButton("szenen", "Szenen")}
          ${this._navButton("steuerung", "Steuerung")}
          <div class="grp">Service</div>
          ${this._navButton("tagesverlauf", "Tagesverlauf")}
          ${this._navButton("protokoll", "Protokoll")}
          ${this._navButton("anlage", "Anlage")}
        </nav>
        <main>${this._viewHtml()}</main>
      </div>
      ${
        this._dialog === "add"
          ? this._addDialogHtml()
          : this._dialog
          ? this._lampDialogHtml()
          : ""
      }`;

    if (!this._bound) {
      // Genau einmal binden. Der Container bleibt über alle Renderdurchläufe
      // derselbe; bei jedem Rendern erneut zu binden hätte die Handler
      // gestapelt, und ein Umschalter hätte sich selbst wieder aufgehoben.
      this._bound = true;
      app.addEventListener("click", (ev) => this._onClick(ev));
      app.addEventListener("change", (ev) => this._onChange(ev));
      app.addEventListener("input", (ev) => this._onInput(ev));
    }
  }

  _navButton(view, label) {
    return `<button data-nav="${view}" class="${this._view === view ? "on" : ""}">${label}</button>`;
  }

  _crumb() {
    if (this._view === "zone" && this._zoneId) {
      const zone = this.zoneConfig(this._zoneId);
      return zone ? zone.name : "Zone";
    }
    if (this._view === "bedienung" && this._controlId) {
      const control = this.controls.find((c) => c.id === this._controlId);
      if (control) return control.name;
    }
    const zone = this.zoneConfig(this._zoneId);
    const raum = zone ? ` · ${zone.name}` : "";
    return (
      {
        leitstand: "Leitstand", protokoll: "Protokoll", anlage: "Anlage",
        tagesverlauf: "Tagesverlauf",
      }[this._view] ||
      { lampen: "Lampen", szenen: "Szenen", steuerung: "Steuerung" }[this._view] + raum
    );
  }

  _viewHtml() {
    if (this._error) return `<div class="empty">Die Lichtregie antwortet nicht: ${esc(this._error)}</div>`;
    if (!this._config) return `<div class="empty">Anlage wird geladen …</div>`;
    switch (this._view) {
      case "lampen":
        return this._lampsHtml();
      case "szenen":
        return this._scenesHtml();
      case "steuerung":
        return this._controlHtml();
      case "zone":
        return this._scenesHtml();
      case "bedienung":
        return this._controlsHtml();
      case "protokoll":
        return this._journalHtml();
      case "anlage":
        return this._installationHtml();
      case "tagesverlauf":
        return this._daylightHtml();
      default:
        return this._overviewHtml();
    }
  }

  // -- Leitstand ------------------------------------------------------------

  _overviewHtml() {
    if (!this.zones.length) {
      return `<h2>Noch keine Anlage</h2>
        <p class="sub">Die Bereiche aus Home Assistant sind noch nicht eingelesen.</p>
        <div class="row"><button class="btn pri" data-act="discover">Anlage einlesen</button></div>`;
    }

    const tiles = this.zones
      .map((zone) => {
        const st = this.zoneState(zone.id);
        const master = Math.round((st.master || 0) * 100);
        const fault = (st.faults || []).length > 0;
        const label = st.layer_source || st.state || "—";
        return `<button class="zt ${master ? "act" : ""} ${fault ? "fault" : ""}" data-zone="${esc(zone.id)}">
            <span class="lvl ${master ? "" : "off"}">${master ? master + " %" : "aus"}</span>
            <div class="zname">${esc(zone.name)}</div>
            <div class="zstate">${esc(label)}${st.remaining ? " · " + secs(st.remaining) : ""}</div>
            <div class="bar"><i style="width:${master}%"></i></div>
          </button>`;
      })
      .join("");

    return `<h2>Leitstand</h2>
      <p class="sub">Live-Zustand aller Zonen. Balken zeigt die Helligkeit, Text die aktive Ebene.</p>
      <div class="zones">${tiles}</div>
      <div class="row">
        <button class="btn" data-act="discover">Anlage neu einlesen</button>
        <button class="btn" data-act="all-off">Alles aus</button>
      </div>`;
  }

  // -- Zone -----------------------------------------------------------------

  _zoneHtml() {
    const zone = this.zoneConfig(this._zoneId) || this.zones[0];
    if (!zone) return `<div class="empty">Keine Zone vorhanden.</div>`;
    this._zoneId = zone.id;
    const st = this.zoneState(zone.id);

    const scenes = (zone.scenes || [])
      .map(
        (scene) => `<div class="srow ${
          this._editScene === scene.id ? "on" : st.scene_id === scene.id ? "on" : ""
        }">
          <span class="dot"></span>
          <button class="btn" data-scene="${esc(scene.id)}" style="border:0;background:none;padding:0">
            ${esc(scene.name)}</button>
          <span class="meta">${scene.fade} s</span>
          <button class="btn" data-edit="${esc(scene.id)}" style="padding:3px 9px;font-size:11px">
            ${this._editScene === scene.id ? "bearbeitet" : "bearbeiten"}</button>
          <button class="del" data-delscene="${esc(scene.id)}" title="Szene löschen"
            style="width:24px">×</button>
        </div>`
      )
      .join("");

    const editing = this._editScene
      ? (zone.scenes || []).find((sc) => sc.id === this._editScene)
      : null;
    const sceneLevels = {};
    if (editing) {
      for (const step of editing.steps || []) sceneLevels[step.circuit_id] = step.level;
    }

    const faders = (zone.circuits || [])
      .map((circuit) => {
        const source = editing ? sceneLevels : st.levels || {};
        const raw = this._dirty && this._draft[circuit.id] !== undefined
          ? this._draft[circuit.id]
          : source[circuit.id] || 0;
        const value = Math.round(raw * 100);
        return `<div class="fader">
            <span class="fname">${esc(circuit.name)}</span>
            <input type="range" min="0" max="100" value="${value}" data-circuit="${esc(circuit.id)}">
            <span class="fval" data-val="${esc(circuit.id)}">${value ? value + " %" : "aus"}</span>
            <span class="role ${esc(circuit.role)}">${esc(ROLE_LABEL[circuit.role] || circuit.role)}</span>
          </div>`;
      })
      .join("");

    const stack = (st.stack || [])
      .map(
        (layer) => `<div class="layer ${layer.active ? "act" : layer.claimed ? "" : "dim"}">
          <span class="p">${layer.layer}</span>
          <span>${esc(layer.label)}<div class="src">${esc(layer.source || "—")}</div></span>
          <span class="ttl">${layer.remaining !== null && layer.remaining !== undefined ? secs(layer.remaining) : layer.claimed ? "ohne Ablauf" : ""}</span>
          <span>${layer.claimed && !layer.active ? `<button class="btn" data-release="${layer.layer}">frei</button>` : ""}</span>
        </div>`
      )
      .join("");

    const picker = this.zones
      .map(
        (z) => `<button class="btn ${z.id === zone.id ? "on" : ""}" data-zone="${esc(z.id)}">${esc(z.name)}</button>`
      )
      .join("");

    return `<h2>${esc(zone.name)}</h2>
      <p class="sub">${esc(zone.kind)} · ${(zone.circuits || []).length} Lichtkreise ·
        ${st.lux !== null && st.lux !== undefined ? Math.round(st.lux) + " lx gemessen" : "kein Helligkeitswert"} ·
        Zustand ${esc(st.state || "unbekannt")}</p>
      <div class="row">${picker}</div>

      <div class="sec">Szenen</div>
      ${scenes || `<div class="empty">Noch keine Szenen. <button class="btn pri" data-act="suggest">Vorschläge erzeugen</button></div>`}

      <div class="sec">Lichtkreise${
        editing ? ` — Szene „${esc(editing.name)}“ wird bearbeitet` : ""
      }</div>
      <div class="faders">${faders}</div>
      <div class="row">
        ${
          editing
            ? `<button class="btn pri" data-act="save-scene" ${this._dirty ? "" : "disabled"}>
                 ${this._dirty ? "Szene speichern" : "gespeichert"}</button>
               <button class="btn" data-act="cancel-edit">Bearbeiten beenden</button>`
            : `<button class="btn" data-act="new-scene">Aktuelles Licht als neue Szene</button>`
        }
        <button class="btn" data-act="snapshot">Ist-Zustand übernehmen</button>
        ${this._busy ? `<span class="chip warn">${esc(this._busy)}</span>` : ""}
      </div>

      <div class="sec">Prioritätsstapel</div>
      <div class="stack">${stack || `<div class="empty">Kein Zustand vorhanden.</div>`}</div>

      <div class="row">
        <button class="btn" data-act="suggest">Szenen vorschlagen</button>
        <button class="btn" data-act="next">Weiterschalten</button>
        <button class="btn pri" data-act="off">Zone aus</button>
      </div>`;
  }

  // -- Raumleiste -----------------------------------------------------------

  _zonePicker() {
    if (!this._zoneId && this.zones.length) this._zoneId = this.zones[0].id;
    return `<div class="zonebar">${this.zones
      .map(
        (z) =>
          `<button class="btn ${z.id === this._zoneId ? "on" : ""}" data-zone="${esc(z.id)}">${esc(z.name)}</button>`
      )
      .join("")}</div>`;
  }

  // -- Lampen ---------------------------------------------------------------

  _lampsHtml() {
    const zone = this.zoneConfig(this._zoneId) || this.zones[0];
    if (!zone) return `<div class="empty">Keine Zone vorhanden.</div>`;
    this._zoneId = zone.id;

    const rollen = [
      ["general", "Deckenlicht"],
      ["task", "Arbeitslicht"],
      ["ambient", "Stimmungslicht"],
      ["accent", "Akzentlicht"],
      ["night", "Orientierung"],
      ["effect", "kein Raumlicht"],
    ];

    const zeilen = (zone.circuits || [])
      .map((circuit) => {
        const f = (circuit.fixtures || [])[0] || {};
        const kannFarbe = f.color_temp || f.color;
        // Fehlt der Wert (ältere Konfiguration), gilt geregelt.
        const fuehrtFarbe = f.manage_color !== false;
        const max = Math.round((f.max_flux ?? 1) * 100);
        const min = Math.round((f.min_flux ?? 0.01) * 100);
        // Nicht "rollen" nennen — das ist oben die Liste aller Auswahlmöglichkeiten.
        const eigene = circuit.roles && circuit.roles.length ? circuit.roles : [circuit.role];
        const haupt = eigene[0];
        const symbol = circuit.icon || ROLE_DEFAULT_ICON[haupt] || "💡";
        return `<div class="lamp ${circuit.enabled ? "" : "off"}"
            data-lampdlg="${esc(circuit.id)}" title="Einstellungen öffnen">
          <div>
            <div class="lname">
              <span class="sym">${esc(symbol)}</span>
              <span class="nam">${esc(circuit.name)}</span>
              ${f.dimmable ? "" : `<span class="kann">· nicht dimmbar</span>`}
            </div>
            <div class="lent">${esc(f.entity_id || "")}${
              eigene.length > 1
                ? ` · <span class="rollen">${eigene
                    .map((r) => esc(ROLE_LABEL[r] || r))
                    .join(" + ")}</span>`
                : ""
            }</div>
          </div>
          <select data-lamp="${esc(circuit.id)}" data-field="role">
            ${rollen
              .map(
                ([v, l]) =>
                  `<option value="${v}" ${v === haupt ? "selected" : ""}>${l}</option>`
              )
              .join("")}
          </select>
          <div>${
            kannFarbe
              ? `<button class="toggle ${fuehrtFarbe ? "on" : ""}"
                   data-lampflag="${esc(circuit.id)}" data-field="manage_color"><i></i>${
                  fuehrtFarbe ? "regeln" : "fest"
                }</button>`
              : `<span class="kann">keine Farbe</span>`
          }</div>
          <div class="num">
            <input type="number" min="1" max="100" value="${max}"
              data-lampnum="${esc(circuit.id)}" data-field="max_flux"
              ${f.dimmable ? "" : "disabled"}>
            <span class="unit">%</span>
          </div>
          <div class="num">
            <input type="number" min="0" max="99" value="${min}"
              data-lampnum="${esc(circuit.id)}" data-field="min_flux"
              ${f.dimmable ? "" : "disabled"}>
            <span class="unit">%</span>
          </div>
          <div>
            <button class="toggle ${f.glares ? "on" : ""}"
              data-lampflag="${esc(circuit.id)}" data-field="glares"><i></i>${
          f.glares ? "blendet" : "frei"
        }</button>
          </div>
        </div>`;
      })
      .join("");

    return `<h2>Lampen</h2>
      <p class="sub">Was für eine Leuchte ist das, soll die Software ihre Farbe führen,
        und was bedeutet volle Helligkeit? Änderungen wirken sofort.</p>
      ${this._zonePicker()}
      <div class="lamp head">
        <span>Leuchte</span><span>Art</span><span>Farbe</span>
        <span>Maximum</span><span>Minimum</span><span>Blendung</span>
      </div>
      ${zeilen || `<div class="empty">Keine Leuchten in dieser Zone.</div>`}
      <div class="row">
        <button class="btn" data-act="add-light">Leuchte hinzufügen</button>
        <span class="ent">Auf einen Namen klicken öffnet alle Einstellungen.</span>
      </div>
      <p class="hint">
        <b>Maximum</b> ist das, was ein Sollwert von 100 % ausmacht — stehen deine Leuchten
        nie über 40 %, trägst du hier 40 ein, und „volle Szene" heißt danach genau das.<br>
        <b>Minimum</b> ist der kleinste Wert, bei dem die Leuchte noch sauber brennt;
        darunter wird ausgeschaltet statt zu flackern.<br>
        <b>Blendung</b> sperrt die Leuchte im Nachtfenster.
      </p>
      ${this._busy ? `<div class="row"><span class="chip warn">${esc(this._busy)}</span></div>` : ""}`;
  }

  // -- Dialog: eine Leuchte -------------------------------------------------

  _lampDialogHtml() {
    const zone = this.zoneConfig(this._zoneId);
    const circuit = (zone.circuits || []).find((c) => c.id === this._dialog);
    if (!circuit) return "";
    const f = (circuit.fixtures || [])[0] || {};
    const rollen = circuit.roles && circuit.roles.length ? circuit.roles : [circuit.role];
    const symbol = circuit.icon || ROLE_DEFAULT_ICON[rollen[0]] || "💡";
    const kannFarbe = f.color_temp || f.color;

    const alleRollen = [
      ["general", "Deckenlicht"],
      ["task", "Arbeitslicht"],
      ["ambient", "Stimmungslicht"],
      ["accent", "Akzentlicht"],
      ["night", "Orientierung"],
      ["effect", "kein Raumlicht"],
    ];

    return `<div class="overlay" data-close="1">
      <div class="dialog" data-stop="1">
        <header>
          <span class="ic">${esc(symbol)}</span>
          <div>
            <h3>${esc(circuit.name)}</h3>
            <div class="ent">${esc(f.entity_id || "")}</div>
          </div>
          <button class="x" data-close="1" title="Schließen">×</button>
        </header>
        <div class="dlgbody">
          <div class="feld">
            <label>Name</label>
            <input type="text" value="${esc(circuit.name)}" data-dlg="name">
          </div>

          <div class="feld">
            <label>Symbol</label>
            <div class="iconwahl">
              ${ROLE_ICONS.map(
                (i) =>
                  `<button class="iconbtn ${i === symbol ? "on" : ""}" data-dlgicon="${esc(i)}">${i}</button>`
              ).join("")}
            </div>
          </div>

          <div class="feld">
            <label>Aufgaben — mehrere möglich, die erste ist die hauptsächliche</label>
            <div class="chips">
              ${alleRollen
                .map(
                  ([wert, text]) =>
                    `<button class="chipbtn ${rollen.includes(wert) ? "on" : ""} ${
                      rollen[0] === wert ? "haupt" : ""
                    }" data-dlgrole="${wert}">${text}</button>`
                )
                .join("")}
            </div>
            <p class="hint">Eine Dekolampe kann Akzentlicht sein und nachts Orientierung.
              Klick auf eine gewählte Aufgabe macht sie zur hauptsächlichen, nochmal klicken
              entfernt sie.</p>
          </div>

          <div class="feld">
            <label>Helligkeit</label>
            <div class="zeile">
              <span class="unit">Maximum</span>
              <input type="number" min="1" max="100" style="width:76px"
                value="${Math.round((f.max_flux ?? 1) * 100)}" data-dlgnum="max_flux"
                ${f.dimmable ? "" : "disabled"}>
              <span class="unit">%</span>
              <span class="unit" style="margin-left:14px">Minimum</span>
              <input type="number" min="0" max="99" style="width:76px"
                value="${Math.round((f.min_flux ?? 0.01) * 100)}" data-dlgnum="min_flux"
                ${f.dimmable ? "" : "disabled"}>
              <span class="unit">%</span>
            </div>
            <p class="hint">${
              f.dimmable
                ? "Maximum ist das, was volle Szenenhelligkeit bedeutet."
                : "Diese Leuchte kann nur an und aus."
            }</p>
          </div>

          <div class="feld">
            <label>Verhalten</label>
            <div class="chips">
              ${
                kannFarbe
                  ? `<button class="chipbtn ${f.manage_color !== false ? "on" : ""}"
                       data-dlgflag="manage_color">Farbtemperatur regeln</button>`
                  : ""
              }
              <button class="chipbtn ${f.glares ? "on" : ""}" data-dlgflag="glares">
                Blendet — nachts sperren</button>
              <button class="chipbtn ${f.night_capable ? "on" : ""}" data-dlgflag="night_capable">
                Als Nachtlicht erlaubt</button>
              <button class="chipbtn ${circuit.enabled ? "on" : ""}" data-dlgenabled="1">
                ${circuit.enabled ? "wird gesteuert" : "abgeschaltet"}</button>
            </div>
          </div>
        </div>
        <footer>
          <button class="btn pri" data-close="1">Fertig</button>
          <button class="btn weg" data-dlgdelete="${esc(circuit.id)}">Aus der Zone entfernen</button>
        </footer>
      </div>
    </div>`;
  }

  // -- Dialog: Leuchte hinzufügen --------------------------------------------

  _addDialogHtml() {
    const zone = this.zoneConfig(this._zoneId);
    const frei = this._freeLights || [];
    const imBereich = frei.filter((l) => l.im_bereich);
    const rest = frei.filter((l) => !l.im_bereich);

    const liste = (titel, eintraege) =>
      eintraege.length
        ? `<div class="feld"><label>${titel}</label>
             <div class="slist">${eintraege
               .map(
                 (l) => `<button class="srow" data-addlight="${esc(l.entity_id)}">
                   <span class="dot"></span>${esc(l.name)}
                   <span class="meta">${esc(l.entity_id)}</span></button>`
               )
               .join("")}</div></div>`
        : "";

    return `<div class="overlay" data-close="1">
      <div class="dialog" data-stop="1">
        <header>
          <span class="ic">＋</span>
          <div><h3>Leuchte zu ${esc(zone ? zone.name : "")} hinzufügen</h3>
            <div class="ent">${frei.length} noch nicht zugeordnet</div></div>
          <button class="x" data-close="1">×</button>
        </header>
        <div class="dlgbody">
          ${
            frei.length
              ? liste("Im Bereich dieser Zone", imBereich) + liste("Übrige", rest)
              : `<div class="empty">Alle Leuchten sind bereits zugeordnet.</div>`
          }
        </div>
        <footer><button class="btn" data-close="1">Schließen</button></footer>
      </div>
    </div>`;
  }

  // -- Szenen ---------------------------------------------------------------

  _scenesHtml() {
    const zone = this.zoneConfig(this._zoneId) || this.zones[0];
    if (!zone) return `<div class="empty">Keine Zone vorhanden.</div>`;
    this._zoneId = zone.id;
    const st = this.zoneState(zone.id);
    const kreise = (zone.circuits || []).filter((c) => c.enabled);

    // Welche Rollen kommen in dieser Zone überhaupt vor?
    const rollenInZone = [];
    for (const c of kreise) {
      for (const r of c.roles && c.roles.length ? c.roles : [c.role]) {
        if (!rollenInZone.includes(r)) rollenInZone.push(r);
      }
    }
    const reihenfolge = ["general", "task", "ambient", "accent", "night", "effect"];
    rollenInZone.sort((a, b) => reihenfolge.indexOf(a) - reihenfolge.indexOf(b));

    const scenes = (zone.scenes || [])
      .map((scene) => {
        const anzahl = Object.keys(this._sceneLevels(zone, scene)).length;
        return `<div class="srow ${
          this._editScene === scene.id ? "on" : st.scene_id === scene.id ? "on" : ""
        }">
          <span class="dot"></span>
          <button class="btn" data-scene="${esc(scene.id)}" style="border:0;background:none;padding:0">
            ${esc(scene.name)}</button>
          <span class="meta">${anzahl} Leuchten${
            Object.keys(scene.overrides || {}).length
              ? ` · ${Object.keys(scene.overrides).length} Ausnahme(n)`
              : ""
          } · ${scene.fade} s</span>
          <button class="btn" data-edit="${esc(scene.id)}" style="padding:3px 9px;font-size:11px">
            ${this._editScene === scene.id ? "bearbeitet" : "bearbeiten"}</button>
          <button class="del" data-delscene="${esc(scene.id)}" title="Szene löschen">×</button>
        </div>`;
      })
      .join("");

    const editing = this._editScene
      ? (zone.scenes || []).find((sc) => sc.id === this._editScene)
      : null;

    if (!editing) {
      return `<h2>Szenen</h2>
        <p class="sub">Eine Szene wird in Ebenen eingestellt: Deckenlicht, Arbeitslicht,
          Stimmung. Einzelne Leuchten können davon abweichen.</p>
        ${this._zonePicker()}
        <div class="slist">${scenes || `<div class="empty">Noch keine Szenen.</div>`}</div>
        <div class="row">
          <button class="btn pri" data-act="suggest">Szenen vorschlagen</button>
          <button class="btn" data-act="new-scene">Aktuelles Licht als neue Szene</button>
          <button class="btn" data-act="off">Zone aus</button>
        </div>
        ${this._busy ? `<div class="row"><span class="chip warn">${esc(this._busy)}</span></div>` : ""}`;
    }

    // --- Bearbeiten -------------------------------------------------------
    const entwurf = this._draft.levels || { ...(editing.levels || {}) };
    const ausnahmen = this._draft.overrides || { ...(editing.overrides || {}) };

    const rollenRegler = rollenInZone
      .map((rolle) => {
        const wert = Math.round((entwurf[rolle] ?? 0) * 100);
        const zahl = kreise.filter((c) =>
          (c.roles && c.roles.length ? c.roles : [c.role]).includes(rolle)
        ).length;
        return `<div class="fader">
          <span class="fname">${esc(ROLE_LABEL[rolle] || rolle)}<br>
            <span class="ent">${zahl} Leuchte${zahl === 1 ? "" : "n"}</span></span>
          <input type="range" min="0" max="100" value="${wert}" data-rolle="${esc(rolle)}">
          <span class="fval" data-rval="${esc(rolle)}">${wert ? wert + " %" : "aus"}</span>
          <span class="role ${esc(rolle)}">${esc(ROLE_LABEL[rolle] || rolle)}</span>
        </div>`;
      })
      .join("");

    const ausnahmeZeilen = kreise
      .map((c) => {
        const eigene = c.roles && c.roles.length ? c.roles : [c.role];
        const ausRolle = Math.max(...eigene.map((r) => entwurf[r] ?? 0), 0);
        const hat = Object.prototype.hasOwnProperty.call(ausnahmen, c.id);
        const wert = Math.round((hat ? ausnahmen[c.id] : ausRolle) * 100);
        return `<div class="rule" style="grid-template-columns:minmax(160px,1.4fr) 150px 120px 30px">
          <div class="src">${esc(c.icon || ROLE_DEFAULT_ICON[eigene[0]] || "💡")} ${esc(c.name)}
            <div class="ent">${eigene.map((r) => esc(ROLE_LABEL[r] || r)).join(" + ")}</div></div>
          <div class="num">
            <input type="number" min="0" max="100" value="${wert}" data-aus="${esc(c.id)}"
              ${hat ? "" : 'style="opacity:.55"'}>
            <span class="unit">%</span>
          </div>
          <div>${
            hat
              ? `<span class="chip warn">Ausnahme</span>`
              : `<span class="ent">folgt der Rolle (${Math.round(ausRolle * 100)} %)</span>`
          }</div>
          <button class="del" data-ausweg="${esc(c.id)}" title="Ausnahme aufheben"
            ${hat ? "" : 'style="opacity:.3"'}>×</button>
        </div>`;
      })
      .join("");

    return `<h2>Szenen</h2>
      <p class="sub">Eine Szene wird in Ebenen eingestellt. Einzelne Leuchten können abweichen.</p>
      ${this._zonePicker()}
      <div class="slist">${scenes}</div>

      <div class="sec">„${esc(editing.name)}“ — Ebenen</div>
      <div class="faders">${rollenRegler}</div>
      <p class="hint">Ein Regler stellt alle Leuchten dieser Aufgabe zugleich.
        Kommt später eine Leuchte dazu, ist sie automatisch dabei.</p>

      <div class="row">
        <button class="btn pri" data-act="save-scene" ${this._dirty ? "" : "disabled"}>
          ${this._dirty ? "Szene speichern" : "gespeichert"}</button>
        <button class="btn" data-act="cancel-edit">Bearbeiten beenden</button>
        <button class="btn" data-act="snapshot">Ist-Zustand übernehmen</button>
        <button class="btn ${this._showOverrides ? "on" : ""}" data-act="toggle-overrides">
          Einzelne Leuchten${
            Object.keys(ausnahmen).length ? ` (${Object.keys(ausnahmen).length})` : ""
          }</button>
        ${this._busy ? `<span class="chip warn">${esc(this._busy)}</span>` : ""}
      </div>

      ${
        this._showOverrides
          ? `<div class="sec">Abweichende Leuchten</div>
             <p class="hint" style="margin-bottom:10px">Eine Zahl eintragen macht die Leuchte
               zur Ausnahme; 0 nimmt sie aus der Szene heraus. Das × stellt sie zurück
               auf ihren Rollenwert.</p>
             ${ausnahmeZeilen}`
          : ""
      }`;
  }

  // Sollwerte je Lichtkreis — dieselbe Rechnung wie im Kern.
  _sceneLevels(zone, scene) {
    const out = {};
    for (const c of zone.circuits || []) {
      if (!c.enabled) continue;
      const eigene = c.roles && c.roles.length ? c.roles : [c.role];
      let wert;
      if (scene.overrides && Object.prototype.hasOwnProperty.call(scene.overrides, c.id)) {
        wert = scene.overrides[c.id];
      } else {
        wert = Math.max(...eigene.map((r) => (scene.levels || {})[r] ?? 0), 0);
      }
      if (wert > 0) out[c.id] = wert;
    }
    return out;
  }

  // -- Steuerung ------------------------------------------------------------

  _controlHtml() {
    const zone = this.zoneConfig(this._zoneId) || this.zones[0];
    if (!zone) return `<div class="empty">Keine Zone vorhanden.</div>`;
    this._zoneId = zone.id;

    const szenen = zone.scenes || [];
    if (!szenen.length) {
      return `<h2>Steuerung</h2>
        ${this._zonePicker()}
        <div class="empty">Erst Szenen anlegen — ohne sie gibt es nichts zu schalten.<br>
          <button class="btn pri" data-act="to-scenes" style="margin-top:12px">Zu den Szenen</button>
        </div>`;
    }

    const szenenWahl = (gewaehlt) =>
      szenen
        .map(
          (sc) =>
            `<option value="${esc(sc.id)}" ${sc.id === gewaehlt ? "selected" : ""}>${esc(sc.name)}</option>`
        )
        .join("");

    // Bewegungsregeln der Zone
    const bewegung = (zone.bindings || []).filter(
      (b) => (b.trigger || {}).art === "bewegung"
    );
    const melder = zone.presence_entities || [];

    const bewegungszeilen = bewegung
      .map(
        (b, i) => `<div class="rule">
          <div class="src">Bewegung
            <div class="ent">${esc(melder.join(", ") || "kein Melder")}</div></div>
          <select data-mo="${i}" data-field="scene_id">${szenenWahl(b.scene_id)}</select>
          <div class="num">
            <input type="number" min="1" max="120" value="${Math.round((b.hold_seconds || zone.linger) / 60)}"
              data-mo="${i}" data-field="minutes"><span class="unit">min</span>
          </div>
          <select data-mo="${i}" data-field="nur_nachts">
            <option value="" ${!(b.conditions || {}).hasOwnProperty("nur_nachts") ? "selected" : ""}>immer</option>
            <option value="ja" ${(b.conditions || {}).nur_nachts === true ? "selected" : ""}>nur nachts</option>
            <option value="nein" ${(b.conditions || {}).nur_nachts === false ? "selected" : ""}>nur tags</option>
          </select>
          <button class="del" data-delmo="${esc(b.id)}" title="Regel löschen">×</button>
        </div>`
      )
      .join("");

    // Bedieneinheit der Zone
    const geraete = this.controls.filter((c) => c.zone_id === zone.id);
    const gewaehlt =
      this._controlId && geraete.some((c) => c.id === this._controlId)
        ? this._controlId
        : (geraete.find((c) => c.buttons >= 2) || geraete[0] || {}).id;
    const control = geraete.find((c) => c.id === gewaehlt);

    const tasten = control
      ? Array.from({ length: Math.max(2, control.buttons) }, (_, i) =>
          control.source === "device_trigger" ? `button_${i + 1}` : String(i + 1)
        )
      : [];
    const gesten = ["tippen", "doppelt", "lang"];

    const tastenzeilen = control
      ? (control.bindings || [])
          .map(
            (b, i) => `<div class="rule">
          <select data-ta="${i}" data-field="taste">
            ${tasten
              .map(
                (t) =>
                  `<option value="${t}" ${t === (b.trigger || {}).taste ? "selected" : ""}>${t.replace("button_", "Taste ")}</option>`
              )
              .join("")}
          </select>
          <select data-ta="${i}" data-field="geste">
            ${gesten
              .map(
                (g) =>
                  `<option value="${g}" ${g === (b.trigger || {}).geste ? "selected" : ""}>${g}</option>`
              )
              .join("")}
          </select>
          <select data-ta="${i}" data-field="action">
            <option value="scene" ${b.action === "scene" ? "selected" : ""}>Szene</option>
            <option value="zone_aus" ${b.action === "zone_aus" ? "selected" : ""}>Aus</option>
            <option value="weiter" ${b.action === "weiter" ? "selected" : ""}>nächste Szene</option>
            <option value="etage_aus" ${b.action === "etage_aus" ? "selected" : ""}>Etage aus</option>
          </select>
          <div>${
            b.action === "scene"
              ? `<select data-ta="${i}" data-field="scene_id">${szenenWahl(b.scene_id)}</select>`
              : `<span class="ent">—</span>`
          }</div>
          <button class="del" data-delta="${esc(b.id)}" title="Belegung löschen">×</button>
        </div>`
          )
          .join("")
      : "";

    return `<h2>Steuerung</h2>
      <p class="sub">Was löst in diesem Raum welche Szene aus.</p>
      ${this._zonePicker()}

      <div class="sec">Bewegungsmelder</div>
      ${
        melder.length
          ? `<div class="rule head"><span>Auslöser</span><span>Szene</span><span>Nachlauf</span>
               <span>Bedingung</span><span></span></div>
             ${bewegungszeilen || `<div class="empty">Noch keine Regel.</div>`}
             <div class="row"><button class="btn" data-act="add-motion">Bewegungsregel hinzufügen</button></div>`
          : `<div class="empty">In dieser Zone ist kein Bewegungsmelder zugeordnet.</div>`
      }

      <div class="sec">Bedieneinheit</div>
      ${
        geraete.length
          ? `<div class="row" style="margin-top:0">
               <select data-field="unit">
                 ${geraete
                   .map(
                     (c) =>
                       `<option value="${esc(c.id)}" ${c.id === gewaehlt ? "selected" : ""}>${esc(c.name)} (${c.buttons} Tasten)</option>`
                   )
                   .join("")}
               </select>
               ${control && control.direct_bound ? `<span class="chip warn">direkt gebunden</span>` : ""}
             </div>
             <div class="rule head" style="margin-top:10px"><span>Taste</span><span>Geste</span>
               <span>Wirkung</span><span>Szene</span><span></span></div>
             ${tastenzeilen || `<div class="empty">Noch keine Belegung.</div>`}
             <div class="row">
               <button class="btn" data-act="add-key">Belegung hinzufügen</button>
               ${this._templates
                 .map(
                   (t) =>
                     `<button class="btn" data-template="${esc(t.key)}" title="${esc(t.beschreibung)}">${esc(t.name)}</button>`
                 )
                 .join("")}
             </div>
             <p class="hint">Die Vorlagen ersetzen die gesamte Belegung dieser Bedieneinheit.
               ${
                 control && control.direct_bound
                   ? `<br><b>Achtung:</b> Dieser Sender schaltet über Zigbee direkt an Home Assistant vorbei.
                      Solange diese Bindung besteht, gewinnt bei jedem Druck das Gerät.`
                   : ""
               }</p>`
          : `<div class="empty">Dieser Zone ist kein Bedienelement zugeordnet.
               <br><span class="ent">Unter „Anlage" siehst du, welche es gibt.</span></div>`
      }
      ${this._busy ? `<div class="row"><span class="chip warn">${esc(this._busy)}</span></div>` : ""}`;
  }

  // -- Bedienelemente -------------------------------------------------------

  _controlsHtml() {
    if (!this.controls.length) {
      return `<h2>Bedienelemente</h2>
        <p class="sub">Noch nichts gefunden.</p>
        <div class="row"><button class="btn pri" data-act="discover">Suchen</button></div>`;
    }
    if (this._controlId) return this._controlDetailHtml();

    const rows = this.controls
      .map((control) => {
        const zone = this.zoneConfig(control.zone_id);
        return `<tr>
          <td><button class="btn" data-control="${esc(control.id)}">${esc(control.name)}</button>
              <div class="mono">${esc(control.model)}</div></td>
          <td>${esc({ device_trigger: "Geräteauslöser", event_entity: "Ereignis-Entität", binary_sensor: "Kontakteingang" }[control.source] || control.source)}</td>
          <td>${control.buttons}</td>
          <td>${zone ? esc(zone.name) : "<span style='color:var(--red)'>keine Zone</span>"}</td>
          <td>${(control.bindings || []).length}</td>
          <td>${control.direct_bound ? `<span class="chip warn">direkt gebunden</span>` : ""}</td>
        </tr>`;
      })
      .join("");

    const bound = this.controls.filter((c) => c.direct_bound);

    return `<h2>Bedienelemente</h2>
      <p class="sub">Alle Taster, Wandsender und Eingänge — herstellerunabhängig auf ein Vokabular normalisiert.
        Auf den Namen klicken, um die Tasten zu belegen.</p>
      <table>
        <thead><tr><th>Gerät</th><th>Quelle</th><th>Tasten</th><th>Zone</th><th>Bindungen</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <div class="learn">
        Lernmodus: eine beliebige Taste drücken. Zuletzt empfangen:
        ${this._lastGesture
          ? `<b>${esc(this._lastGesture.control)} · Taste ${esc(this._lastGesture.button)} · ${esc(this._lastGesture.gesture)}</b>
             <span class="mono"> (roh: ${esc(this._lastGesture.raw)})</span>`
          : "noch nichts"}
      </div>
      ${
        bound.length
          ? `<div class="sec">Direktbindung</div>
             <p class="sub">${bound.length} Sender schalten über Zigbee direkt an Home Assistant vorbei.
             Solange das so ist, gewinnt bei jedem Tastendruck das Gerät gegen die Engine.</p>
             <table><thead><tr><th>Sender</th><th>Gebundene Gruppen</th></tr></thead><tbody>
             ${bound
               .map(
                 (c) =>
                   `<tr><td><b>${esc(c.name)}</b></td><td class="mono">${esc((c.direct_groups || []).join(", "))}</td></tr>`
               )
               .join("")}
             </tbody></table>`
          : ""
      }`;
  }

  // -- Bindungseditor -------------------------------------------------------

  _controlDetailHtml() {
    const control = this.controls.find((c) => c.id === this._controlId);
    if (!control) return `<div class="empty">Bedienelement nicht gefunden.</div>`;
    const zone = this.zoneConfig(control.zone_id);

    const buttons = Array.from({ length: Math.max(2, control.buttons) }, (_, i) =>
      control.source === "device_trigger" ? `button_${i + 1}` : String(i + 1)
    );
    const gestures = ["tippen", "doppelt", "dreifach", "lang", "halten"];
    const actions = [
      ["scene", "Szene aufrufen"],
      ["zone_aus", "Zone aus"],
      ["etage_aus", "Etage aus"],
      ["weiter", "nächste Szene"],
      ["automatik", "Automatik scharf"],
    ];
    const holds = [
      ["solange_belegt", "solange belegt"],
      ["feste_dauer", "feste Dauer"],
      ["bis_leer", "bis Zone leer"],
      ["bis_gegendruck", "bis Gegendruck"],
      ["bis_zeitpunkt", "bis Zeitpunkt"],
      ["bis_andere_szene", "bis andere Szene"],
      ["unbegrenzt", "unbegrenzt"],
    ];
    const options = (list, selected) =>
      list
        .map(
          ([value, label]) =>
            `<option value="${esc(value)}" ${value === selected ? "selected" : ""}>${esc(label)}</option>`
        )
        .join("");

    const scenes = (zone && zone.scenes) || [];

    const rows = (control.bindings || [])
      .map((b, index) => {
        const target =
          b.action === "scene"
            ? `<select data-bind="${index}" data-field="scene_id">
                 ${options(scenes.map((sc) => [sc.id, sc.name]), b.scene_id)}
               </select>`
            : `<span class="mono">—</span>`;
        const duration =
          b.hold === "feste_dauer"
            ? `<input type="number" min="1" max="480" value="${Math.round((b.hold_seconds || 1800) / 60)}"
                 data-bind="${index}" data-field="hold_minutes" style="width:58px"> min`
            : b.hold === "bis_zeitpunkt"
            ? `<input type="text" value="${esc(b.until || "23:00")}" data-bind="${index}" data-field="until" style="width:66px">`
            : "";
        return `<div class="bind">
          <select data-bind="${index}" data-field="taste">
            ${options(buttons.map((x) => [x, x.replace("button_", "Taste ")]), b.trigger.taste)}
          </select>
          <select data-bind="${index}" data-field="geste">
            ${options(gestures.map((g) => [g, g]), b.trigger.geste)}
          </select>
          <div style="display:flex;gap:7px;align-items:center">
            <select data-bind="${index}" data-field="action">${options(actions, b.action)}</select>
            ${target}
          </div>
          <div style="display:flex;gap:7px;align-items:center">
            <select data-bind="${index}" data-field="hold">${options(holds, b.hold)}</select>
            ${duration}
          </div>
          <select data-bind="${index}" data-field="nur_nachts">
            ${options(
              [["", "immer"], ["ja", "nur nachts"], ["nein", "nur tags"]],
              b.conditions && b.conditions.nur_nachts === true
                ? "ja"
                : b.conditions && b.conditions.nur_nachts === false
                ? "nein"
                : ""
            )}
          </select>
          <button class="del" data-delbind="${esc(b.id)}" title="Bindung löschen">×</button>
        </div>`;
      })
      .join("");

    const templates = this._templates
      .map(
        (t) => `<button class="tcard" data-template="${esc(t.key)}">
          <b>${esc(t.name)}</b><span>${esc(t.beschreibung)}</span></button>`
      )
      .join("");

    return `<h2>${esc(control.name)}</h2>
      <p class="sub">${esc(control.model)} · ${control.buttons} Tasten ·
        Zone ${zone ? esc(zone.name) : "<span style='color:var(--red)'>nicht zugeordnet</span>"}
        ${control.direct_bound ? ` · <span style="color:var(--amber)">direkt gebunden an ${esc((control.direct_groups || []).join(", "))}</span>` : ""}</p>
      <div class="row">
        <button class="btn" data-act="controls-back">← Übersicht</button>
        <select data-field="control_zone">
          <option value="">Zone wählen …</option>
          ${this.zones
            .map(
              (z) =>
                `<option value="${esc(z.id)}" ${z.id === control.zone_id ? "selected" : ""}>${esc(z.name)}</option>`
            )
            .join("")}
        </select>
      </div>

      <div class="sec">Tastenbelegung</div>
      ${
        rows
          ? `<div class="bind head"><span>Taste</span><span>Geste</span><span>Wirkung</span>
               <span>Haltedauer</span><span>Bedingung</span><span></span></div>${rows}`
          : `<div class="empty">Noch keine Belegung. Unten eine Vorlage wählen.</div>`
      }
      <div class="row">
        <button class="btn" data-act="add-binding">Bindung hinzufügen</button>
        ${this._busy ? `<span class="chip warn">${esc(this._busy)}</span>` : ""}
      </div>

      <div class="sec">Vorlagen</div>
      <p class="sub">Ersetzt die gesamte Belegung dieses Senders.</p>
      <div class="tmpl">${templates}</div>

      <div class="learn">
        Lernmodus: Taste am Gerät drücken. Zuletzt empfangen:
        ${this._lastGesture
          ? `<b>Taste ${esc(this._lastGesture.button)} · ${esc(this._lastGesture.gesture)}</b>
             <span class="mono"> (roh: ${esc(this._lastGesture.raw)})</span>`
          : "noch nichts"}
      </div>`;
  }

  // -- Tagesverlauf ---------------------------------------------------------

  _daylightHtml() {
    if (!this._curves) {
      this._call("lichtregie/curves", { zone_id: this._zoneId || "" }).then((data) => {
        this._curves = data;
        this._render();
      });
      return `<div class="empty">Kurven werden geladen …</div>`;
    }

    const width = 720;
    const height = 220;
    const curve = this._curves.kurven.find((c) => c.key === this._curves.aktiv) || this._curves.kurven[0];
    const points = curve.verlauf;
    const x = (minute) => 46 + (minute / 1440) * (width - 66);
    const yK = (k) => 190 - ((k - 2000) / 4500) * 165;
    const yF = (f) => 190 - f * 165;

    const line = (fn, key) =>
      points.map((p, i) => `${i ? "L" : "M"}${x(p.minute).toFixed(1)},${fn(p[key]).toFixed(1)}`).join(" ");

    const sunMinute = (iso) => {
      const d = new Date(iso);
      return d.getHours() * 60 + d.getMinutes();
    };
    const rise = sunMinute(this._curves.aufgang);
    const set = sunMinute(this._curves.untergang);

    const picker = this._curves.kurven
      .map(
        (c) =>
          `<button class="btn ${c.key === curve.key ? "on" : ""}" data-curve="${esc(c.key)}">${esc(c.name)}</button>`
      )
      .join("");

    const zoneRows = this.zones
      .map((z) => {
        const st = this.zoneState(z.id);
        const dl = st.daylight || {};
        const cl = st.konstantlicht || {};
        return `<tr>
          <td><b>${esc(z.name)}</b><div class="mono">${esc(dl.kurve || "")}</div></td>
          <td><button class="toggle ${z.daylight ? "on" : ""}" data-toggle="daylight" data-zone-id="${esc(z.id)}">
              <i></i>${z.daylight ? "an" : "aus"}</button></td>
          <td class="mono">${dl.kelvin ? dl.kelvin + " K · Faktor " + dl.faktor : "—"}</td>
          <td><button class="toggle ${z.constant_light ? "on" : ""}" data-toggle="constant_light" data-zone-id="${esc(z.id)}">
              <i></i>${z.constant_light ? "an" : "aus"}</button></td>
          <td>${
            cl.kalibriert
              ? `<span class="chip ok">kalibriert</span>`
              : `<button class="btn" data-calibrate="${esc(z.id)}">Kalibrierfahrt</button>`
          }</td>
          <td class="mono">${Math.round(z.setpoint_lux)} lx</td>
        </tr>`;
      })
      .join("");

    return `<h2>Tagesverlauf</h2>
      <p class="sub">Farbtemperatur und Helligkeitsfaktor über den Tag, gebunden an den Sonnenstand.
        Heute: Aufgang ${new Date(this._curves.aufgang).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })},
        Untergang ${new Date(this._curves.untergang).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}.</p>
      <div class="row">${picker}</div>
      <div class="curvebox" style="margin-top:14px">
        <svg viewBox="0 0 ${width} ${height}" style="width:100%;display:block">
          <g stroke="#282C35" stroke-width="1">
            <line x1="46" y1="25" x2="${width - 20}" y2="25"/>
            <line x1="46" y1="80" x2="${width - 20}" y2="80"/>
            <line x1="46" y1="135" x2="${width - 20}" y2="135"/>
            <line x1="46" y1="190" x2="${width - 20}" y2="190"/>
          </g>
          <g stroke="#3A4049" stroke-dasharray="3 4">
            <line x1="${x(rise)}" y1="20" x2="${x(rise)}" y2="192"/>
            <line x1="${x(set)}" y1="20" x2="${x(set)}" y2="192"/>
          </g>
          <g fill="#646A78" font-family="ui-monospace,monospace" font-size="9">
            <text x="4" y="28">6500 K</text><text x="4" y="83">5000 K</text>
            <text x="4" y="138">3500 K</text><text x="4" y="193">2000 K</text>
            <text x="42" y="208">00</text><text x="${x(360)}" y="208">06</text>
            <text x="${x(720)}" y="208">12</text><text x="${x(1080)}" y="208">18</text>
            <text x="${width - 34}" y="208">24</text>
            <text x="${x(rise) + 4}" y="18" fill="#5FA8D8">Aufgang</text>
            <text x="${x(set) + 4}" y="18" fill="#F0A63C">Untergang</text>
          </g>
          <path d="${line(yF, "factor")}" fill="none" stroke="#5FA8D8" stroke-width="1.8" stroke-dasharray="4 3"/>
          <path d="${line(yK, "kelvin")}" fill="none" stroke="#F0A63C" stroke-width="2.6"/>
        </svg>
        <div class="row" style="margin-top:6px">
          <span class="mono" style="color:var(--amber)">— Farbtemperatur</span>
          <span class="mono" style="color:var(--blue)">- - Helligkeitsfaktor</span>
        </div>
      </div>

      <div class="sec">Zonen</div>
      <table>
        <thead><tr><th>Zone</th><th>Tagesverlauf</th><th>gerade</th>
          <th>Konstantlicht</th><th>Kalibrierung</th><th>Sollwert</th></tr></thead>
        <tbody>${zoneRows}</tbody>
      </table>
      ${this._busy ? `<div class="row"><span class="chip warn">${esc(this._busy)}</span></div>` : ""}`;
  }

  // -- Protokoll ------------------------------------------------------------

  _journalHtml() {
    if (!this._journal.length) return `<div class="empty">Noch keine Einträge.</div>`;
    const rows = this._journal
      .slice(0, 120)
      .map((entry) => {
        const tone = entry.kind === "abweichung" || entry.kind === "fehler" || entry.kind === "stoerung"
          ? "bad"
          : ["einschalten", "ausgabe", "bedienung"].includes(entry.kind)
          ? "hot"
          : "";
        return `<div class="t">${clock(entry.at)}</div>
          <div class="c ${tone}"><b>${esc(entry.headline)}</b>
            <span>${esc(entry.detail)}${entry.layer ? " · Ebene " + entry.layer : ""}</span></div>`;
      })
      .join("");
    return `<h2>Protokoll</h2>
      <p class="sub">Jede Entscheidung mit ihrer Begründung — Auslöser, Messwerte, Ebene, gesendete Werte.</p>
      <div class="tl">${rows}</div>`;
  }

  // -- Anlage ---------------------------------------------------------------

  _installationHtml() {
    const rows = this.zones
      .map((zone) => {
        const st = this.zoneState(zone.id);
        const quality = { regelfaehig: "regelfähig", momentaufnahme: "Momentaufnahme", tot: "tot" }[zone.lux_quality] || zone.lux_quality;
        const color = zone.lux_quality === "regelfaehig" ? "var(--green)" : zone.lux_quality === "tot" ? "var(--red)" : "var(--amber)";
        return `<tr>
          <td><b>${esc(zone.name)}</b><div class="mono">${esc(zone.kind)}</div></td>
          <td>${(zone.circuits || []).length}</td>
          <td>${(zone.presence_entities || []).length}</td>
          <td>${zone.lux_entity ? `<span class="mono">${esc(zone.lux_entity)}</span><div style="color:${color}">${esc(quality)}</div>` : "—"}</td>
          <td>${Math.round(zone.linger / 60)} min</td>
          <td>${(zone.scenes || []).length}</td>
        </tr>`;
      })
      .join("");

    const stats = (this._state && this._state.stats) || {};
    return `<h2>Anlage</h2>
      <p class="sub">Fassung ${this._config.version} · Betriebsart ${esc(this._config.mode)}</p>
      <table>
        <thead><tr><th>Zone</th><th>Kreise</th><th>Melder</th><th>Helligkeitssensor</th><th>Nachlauf</th><th>Szenen</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <div class="sec">Treiber</div>
      <p class="sub">${stats.calls || 0} Aufrufe · ${stats.grouped || 0} zusammengefasst ·
        ${stats.skipped || 0} übersprungen · ${stats.retries || 0} Wiederholungen ·
        ${(stats.faults || []).length} gestört</p>
      <div class="row">
        <button class="btn" data-act="discover">Anlage neu einlesen</button>
        <button class="btn" data-act="suggest-all">Szenen für alle Zonen vorschlagen</button>
      </div>`;
  }

  // -- Ereignisse -----------------------------------------------------------

  async _onClick(ev) {
    const target = ev.target.closest(
      "[data-nav],[data-zone],[data-scene],[data-act],[data-release]," +
        "[data-control],[data-template],[data-delbind],[data-curve],[data-toggle],[data-calibrate]," +
        "[data-edit],[data-delscene],[data-lampflag],[data-delmo],[data-delta]," +
        "[data-lampdlg],[data-close],[data-stop],[data-dlgicon],[data-dlgrole],[data-ausweg]," +
        "[data-dlgflag],[data-dlgenabled],[data-dlgdelete],[data-addlight]"
    );
    if (!target) return;

    // --- Dialog ---------------------------------------------------------
    if (target.dataset.stop) return;
    if (target.dataset.close) {
      this._dialog = null;
      return this._render();
    }
    if (target.dataset.lampdlg) {
      // Auswahlfelder, Zahlen und Schalter in der Zeile bedienen sich selbst.
      if (ev.target.closest("select,input,.toggle,[data-lampflag]")) return;
      this._dialog = target.dataset.lampdlg;
      return this._render();
    }
    if (target.dataset.dlgicon) {
      await this._call("lichtregie/circuit/set", {
        zone_id: this._zoneId,
        circuit_id: this._dialog,
        icon: target.dataset.dlgicon,
      });
      this._config = await this._call("lichtregie/config/get");
      return this._render();
    }
    if (target.dataset.dlgrole) {
      const zone = this.zoneConfig(this._zoneId);
      const circuit = (zone.circuits || []).find((c) => c.id === this._dialog);
      const wert = target.dataset.dlgrole;
      let rollen = [...(circuit.roles || [circuit.role])];
      if (!rollen.includes(wert)) {
        rollen.push(wert);
      } else if (rollen[0] === wert) {
        rollen = rollen.filter((r) => r !== wert);
      } else {
        rollen = [wert, ...rollen.filter((r) => r !== wert)];
      }
      if (!rollen.length) rollen = ["general"];
      await this._call("lichtregie/circuit/set", {
        zone_id: this._zoneId,
        circuit_id: this._dialog,
        roles: rollen,
        enabled: !(rollen.length === 1 && rollen[0] === "effect"),
      });
      this._config = await this._call("lichtregie/config/get");
      return this._render();
    }
    if (target.dataset.dlgflag) {
      const zone = this.zoneConfig(this._zoneId);
      const circuit = (zone.circuits || []).find((c) => c.id === this._dialog);
      const f = (circuit.fixtures || [])[0];
      const feld = target.dataset.dlgflag;
      const aktuell = feld === "manage_color" ? f.manage_color !== false : !!f[feld];
      await this._call("lichtregie/fixture/set", {
        zone_id: this._zoneId,
        circuit_id: circuit.id,
        entity_id: f.entity_id,
        [feld]: !aktuell,
      });
      this._config = await this._call("lichtregie/config/get");
      return this._render();
    }
    if (target.dataset.dlgenabled) {
      const zone = this.zoneConfig(this._zoneId);
      const circuit = (zone.circuits || []).find((c) => c.id === this._dialog);
      await this._call("lichtregie/circuit/set", {
        zone_id: this._zoneId,
        circuit_id: circuit.id,
        enabled: !circuit.enabled,
      });
      this._config = await this._call("lichtregie/config/get");
      return this._render();
    }
    if (target.dataset.dlgdelete) {
      const zone = this.zoneConfig(this._zoneId);
      const circuit = (zone.circuits || []).find((c) => c.id === target.dataset.dlgdelete);
      if (!confirm(`„${circuit.name}" aus ${zone.name} entfernen?`)) return;
      const antwort = await this._call("lichtregie/circuit/delete", {
        zone_id: this._zoneId,
        circuit_id: target.dataset.dlgdelete,
      });
      this._dialog = null;
      this._config = await this._call("lichtregie/config/get");
      this._busy = antwort.leere_szenen
        ? `${antwort.leere_szenen} Szene(n) sind dadurch leer`
        : "";
      return this._render();
    }
    if (target.dataset.addlight) {
      await this._call("lichtregie/circuit/add", {
        zone_id: this._zoneId,
        entity_id: target.dataset.addlight,
      });
      this._config = await this._call("lichtregie/config/get");
      this._freeLights = (
        await this._call("lichtregie/lights/free", { zone_id: this._zoneId })
      ).leuchten;
      return this._render();
    }
    if (target.dataset.ausweg) {
      const ausnahmen = { ...(this._draft.overrides || {}) };
      delete ausnahmen[target.dataset.ausweg];
      this._draft.overrides = ausnahmen;
      this._dirty = true;
      return this._render();
    }
    if (target.dataset.lampflag) {
      const zone = this.zoneConfig(this._zoneId);
      const circuit = (zone.circuits || []).find((c) => c.id === target.dataset.lampflag);
      const f = (circuit.fixtures || [])[0];
      const feld = target.dataset.field;
      await this._call("lichtregie/fixture/set", {
        zone_id: this._zoneId,
        circuit_id: circuit.id,
        entity_id: f.entity_id,
        [feld]: !f[feld],
      });
      this._config = await this._call("lichtregie/config/get");
      return this._render();
    }
    if (target.dataset.delmo) {
      await this._call("lichtregie/binding/delete", {
        zone_id: this._zoneId,
        binding_id: target.dataset.delmo,
      });
      this._config = await this._call("lichtregie/config/get");
      return this._render();
    }
    if (target.dataset.delta) {
      await this._call("lichtregie/binding/delete", {
        control_id: this._activeControlId(),
        binding_id: target.dataset.delta,
      });
      this._config = await this._call("lichtregie/config/get");
      return this._render();
    }
    if (target.dataset.edit) {
      this._editScene = this._editScene === target.dataset.edit ? null : target.dataset.edit;
      this._dirty = false;
      this._draft = {};
      this._busy = "";
      return this._render();
    }
    if (target.dataset.delscene) {
      const scene = (this.zoneConfig(this._zoneId).scenes || []).find(
        (sc) => sc.id === target.dataset.delscene
      );
      if (!confirm(`Szene „${scene ? scene.name : target.dataset.delscene}" löschen?`)) return;
      const answer = await this._call("lichtregie/scene/delete", {
        zone_id: this._zoneId,
        scene_id: target.dataset.delscene,
      });
      this._editScene = null;
      this._config = await this._call("lichtregie/config/get");
      this._busy = answer.bindungen_entfernt
        ? `${answer.bindungen_entfernt} Bindung(en) mit entfernt`
        : "";
      return this._render();
    }
    if (target.dataset.control) {
      this._controlId = target.dataset.control;
      this._view = "bedienung";
      return this._render();
    }
    if (target.dataset.curve) {
      this._curves.aktiv = target.dataset.curve;
      return this._render();
    }
    if (target.dataset.template) {
      this._busy = "Vorlage wird angewendet …";
      this._render();
      try {
        await this._call("lichtregie/template/apply", {
          control_id: this._activeControlId(),
          template: target.dataset.template,
        });
        this._config = await this._call("lichtregie/config/get");
        this._busy = "";
      } catch (err) {
        this._busy = String(err && err.message ? err.message : err);
      }
      return this._render();
    }
    if (target.dataset.delbind) {
      await this._call("lichtregie/binding/delete", {
        control_id: this._controlId,
        binding_id: target.dataset.delbind,
      });
      this._config = await this._call("lichtregie/config/get");
      return this._render();
    }
    if (target.dataset.toggle) {
      const zoneId = target.dataset.zoneId;
      const zone = this.zoneConfig(zoneId);
      const field = target.dataset.toggle;
      await this._call("lichtregie/zone/settings", {
        zone_id: zoneId,
        [field]: !zone[field],
      });
      this._config = await this._call("lichtregie/config/get");
      this._curves = null;
      return this._render();
    }
    if (target.dataset.calibrate) {
      this._busy = "Kalibrierfahrt läuft — bitte den Raum nicht betreten.";
      this._render();
      try {
        const result = await this._call("lichtregie/calibrate", {
          zone_id: target.dataset.calibrate,
        });
        this._busy = result.ok
          ? "Kalibrierfahrt abgeschlossen."
          : `Kalibrierfahrt abgebrochen: ${result.grund || "unbekannt"}`;
        this._config = await this._call("lichtregie/config/get");
        this._state = await this._call("lichtregie/state");
      } catch (err) {
        this._busy = String(err && err.message ? err.message : err);
      }
      return this._render();
    }

    if (target.dataset.nav) {
      this._view = target.dataset.nav;
      this._controlId = null;
      this._busy = "";
      return this._render();
    }
    if (target.dataset.zone) {
      this._zoneId = target.dataset.zone;
      if (!["lampen", "szenen", "steuerung"].includes(this._view)) {
        this._view = "szenen";
      }
      this._editScene = null;
      this._dirty = false;
      this._draft = {};
      this._busy = "";
      return this._render();
    }
    if (target.dataset.scene) {
      await this._call("lichtregie/scene/apply", {
        zone_id: this._zoneId,
        scene_id: target.dataset.scene,
      });
      return;
    }
    if (target.dataset.release) {
      await this._call("lichtregie/layer/release", {
        zone_id: this._zoneId,
        layer: Number(target.dataset.release),
      });
      return;
    }

    switch (target.dataset.act) {
      case "discover": {
        const answer = await this._call("lichtregie/discover", { merge: true });
        this._config = answer.installation || (await this._call("lichtregie/config/get"));
        this._state = await this._call("lichtregie/state");
        return this._render();
      }
      case "suggest": {
        await this._call("lichtregie/scene/suggest", { zone_id: this._zoneId, apply: true });
        this._config = await this._call("lichtregie/config/get");
        return this._render();
      }
      case "suggest-all": {
        for (const zone of this.zones) {
          await this._call("lichtregie/scene/suggest", { zone_id: zone.id, apply: true });
        }
        this._config = await this._call("lichtregie/config/get");
        return this._render();
      }
      case "off":
        return void this._call("lichtregie/zone/off", { zone_id: this._zoneId });
      case "next":
        return void this._call("lichtregie/zone/next", { zone_id: this._zoneId });
      case "toggle-overrides":
        this._showOverrides = !this._showOverrides;
        return this._render();
      case "save-scene": {
        const zone = this.zoneConfig(this._zoneId);
        const scene = (zone.scenes || []).find((sc) => sc.id === this._editScene);
        if (!scene) return;
        await this._call("lichtregie/scene/set", {
          zone_id: this._zoneId,
          scene: {
            ...scene,
            levels: this._draft.levels || scene.levels,
            overrides: this._draft.overrides || scene.overrides,
          },
        });
        this._config = await this._call("lichtregie/config/get");
        this._dirty = false;
        this._draft = {};
        this._busy = "Szene gespeichert.";
        return this._render();
      }
      case "cancel-edit":
        this._editScene = null;
        this._dirty = false;
        this._draft = {};
        this._busy = "";
        return this._render();
      case "new-scene": {
        const name = prompt("Name der neuen Szene?");
        if (!name) return;
        const snapshot = await this._call("lichtregie/scene/snapshot", {
          zone_id: this._zoneId,
        });
        const answer = await this._call("lichtregie/scene/set", {
          zone_id: this._zoneId,
          scene: {
            id: "",
            name,
            levels: snapshot.levels || {},
            overrides: snapshot.overrides || {},
            kelvin: snapshot.kelvin || null,
            fade: 1.5,
          },
        });
        this._config = await this._call("lichtregie/config/get");
        this._editScene = answer.scene ? answer.scene.id : null;
        this._dirty = false;
        this._draft = {};
        return this._render();
      }
      case "snapshot": {
        const snapshot = await this._call("lichtregie/scene/snapshot", {
          zone_id: this._zoneId,
        });
        this._draft = {
          levels: snapshot.levels || {},
          overrides: snapshot.overrides || {},
        };
        this._dirty = !!this._editScene;
        this._busy = this._editScene
          ? "Ist-Zustand übernommen — noch nicht gespeichert."
          : "Ist-Zustand gelesen. Zum Sichern eine Szene bearbeiten.";
        return this._render();
      }
      case "add-light": {
        this._freeLights = (
          await this._call("lichtregie/lights/free", { zone_id: this._zoneId })
        ).leuchten;
        this._dialog = "add";
        return this._render();
      }
      case "to-scenes":
        this._view = "szenen";
        return this._render();
      case "add-motion": {
        const zone = this.zoneConfig(this._zoneId);
        await this._call("lichtregie/binding/set", {
          zone_id: this._zoneId,
          binding: {
            id: `m${Date.now().toString(36)}`,
            trigger: { art: "bewegung" },
            action: "scene",
            scene_id: (zone.scenes[0] || {}).id,
            layer: 40,
            hold: "solange_belegt",
            hold_seconds: zone.linger,
            conditions: {},
          },
        });
        this._config = await this._call("lichtregie/config/get");
        return this._render();
      }
      case "add-key": {
        const zone = this.zoneConfig(this._zoneId);
        const control = this.controls.find((c) => c.id === this._activeControlId());
        if (!control) return;
        const taste = control.source === "device_trigger" ? "button_1" : "1";
        await this._call("lichtregie/binding/set", {
          control_id: control.id,
          binding: {
            id: `t${Date.now().toString(36)}`,
            trigger: { art: "taste", taste, geste: "tippen" },
            action: "scene",
            scene_id: (zone.scenes[0] || {}).id,
            layer: 50,
            hold: "bis_leer",
            conditions: {},
          },
        });
        this._config = await this._call("lichtregie/config/get");
        return this._render();
      }
      case "controls-back":
        this._controlId = null;
        return this._render();
      case "add-binding": {
        const control = this.controls.find((c) => c.id === this._controlId);
        const zone = this.zoneConfig(control && control.zone_id);
        const button = control && control.source === "device_trigger" ? "button_1" : "1";
        await this._call("lichtregie/binding/set", {
          control_id: this._controlId,
          binding: {
            id: `b${Date.now().toString(36)}`,
            trigger: { art: "taste", taste: button, geste: "tippen" },
            action: zone && zone.scenes.length ? "scene" : "zone_aus",
            scene_id: zone && zone.scenes.length ? zone.scenes[0].id : null,
            layer: 50,
            hold: "bis_leer",
          },
        });
        this._config = await this._call("lichtregie/config/get");
        return this._render();
      }
      case "all-off":
        for (const zone of this.zones) {
          await this._call("lichtregie/zone/off", { zone_id: zone.id });
        }
        return;
    }
  }

  async _saveBinding(index, field, value) {
    const control = this.controls.find((c) => c.id === this._controlId);
    if (!control) return;
    const binding = JSON.parse(JSON.stringify(control.bindings[index]));
    if (!binding) return;

    if (field === "taste" || field === "geste") {
      binding.trigger = { ...binding.trigger, art: "taste", [field]: value };
    } else if (field === "hold_minutes") {
      binding.hold_seconds = Math.max(60, Number(value) * 60);
    } else if (field === "nur_nachts") {
      binding.conditions = { ...(binding.conditions || {}) };
      if (value === "") delete binding.conditions.nur_nachts;
      else binding.conditions.nur_nachts = value === "ja";
    } else {
      binding[field] = value;
    }
    if (field === "hold" && value === "feste_dauer" && !binding.hold_seconds) {
      binding.hold_seconds = 1800;
    }

    await this._call("lichtregie/binding/set", {
      control_id: this._controlId,
      binding,
    });
    this._config = await this._call("lichtregie/config/get");
    this._render();
  }

  _aktuelleOverrides() {
    const zone = this.zoneConfig(this._zoneId);
    const scene = (zone.scenes || []).find((sc) => sc.id === this._editScene);
    return { ...((scene && scene.overrides) || {}) };
  }

  _aktuelleLevels() {
    const zone = this.zoneConfig(this._zoneId);
    const scene = (zone.scenes || []).find((sc) => sc.id === this._editScene);
    return { ...((scene && scene.levels) || {}) };
  }

  // Schickt das aktuelle Bild an die Leuchten, aber höchstens alle 250 ms.
  _vorschau() {
    if (this._vorschauTimer) return;
    this._vorschauTimer = setTimeout(() => {
      this._vorschauTimer = null;
      const zone = this.zoneConfig(this._zoneId);
      const scene = (zone.scenes || []).find((sc) => sc.id === this._editScene);
      if (!zone || !scene) return;
      const entwurf = {
        ...scene,
        levels: this._draft.levels || scene.levels,
        overrides: this._draft.overrides || scene.overrides,
      };
      this._call("lichtregie/scene/preview", {
        zone_id: zone.id,
        levels: this._sceneLevels(zone, entwurf),
      });
    }, 250);
  }

  _activeControlId() {
    const geraete = this.controls.filter((c) => c.zone_id === this._zoneId);
    if (this._controlId && geraete.some((c) => c.id === this._controlId)) {
      return this._controlId;
    }
    const wahl = geraete.find((c) => c.buttons >= 2) || geraete[0];
    return wahl ? wahl.id : null;
  }

  async _saveMotion(index, field, value) {
    const zone = this.zoneConfig(this._zoneId);
    const regeln = (zone.bindings || []).filter((b) => (b.trigger || {}).art === "bewegung");
    const b = JSON.parse(JSON.stringify(regeln[index]));
    if (!b) return;
    if (field === "minutes") {
      b.hold_seconds = Math.max(30, Number(value) * 60);
    } else if (field === "nur_nachts") {
      b.conditions = { ...(b.conditions || {}) };
      if (value === "") delete b.conditions.nur_nachts;
      else b.conditions.nur_nachts = value === "ja";
    } else {
      b[field] = value;
    }
    await this._call("lichtregie/binding/set", { zone_id: this._zoneId, binding: b });
    this._config = await this._call("lichtregie/config/get");
    this._render();
  }

  async _saveKey(index, field, value) {
    const control = this.controls.find((c) => c.id === this._activeControlId());
    if (!control) return;
    const b = JSON.parse(JSON.stringify((control.bindings || [])[index]));
    if (!b) return;
    if (field === "taste" || field === "geste") {
      b.trigger = { ...b.trigger, art: "taste", [field]: value };
    } else {
      b[field] = value;
    }
    await this._call("lichtregie/binding/set", { control_id: control.id, binding: b });
    this._config = await this._call("lichtregie/config/get");
    this._render();
  }

  async _saveLamp(circuitId, field, value) {
    const zone = this.zoneConfig(this._zoneId);
    const circuit = (zone.circuits || []).find((c) => c.id === circuitId);
    if (!circuit) return;

    if (field === "role") {
      await this._call("lichtregie/circuit/set", {
        zone_id: this._zoneId,
        circuit_id: circuitId,
        role: value,
        enabled: value !== "effect",
      });
    } else {
      const f = (circuit.fixtures || [])[0];
      const anteil = Math.min(100, Math.max(0, Number(value))) / 100;
      await this._call("lichtregie/fixture/set", {
        zone_id: this._zoneId,
        circuit_id: circuitId,
        entity_id: f.entity_id,
        [field]: anteil,
      });
    }
    this._config = await this._call("lichtregie/config/get");
    this._render();
  }

  _onInput(ev) {
    const rolle = ev.target.closest("input[data-rolle]");
    if (rolle) {
      const wert = Number(rolle.value);
      const anzeige = this.shadowRoot.querySelector(`[data-rval="${rolle.dataset.rolle}"]`);
      if (anzeige) anzeige.textContent = wert ? `${wert} %` : "aus";
      const levels = { ...(this._draft.levels || this._aktuelleLevels()) };
      levels[rolle.dataset.rolle] = wert / 100;
      this._draft = { ...this._draft, levels };
      if (!this._dirty) {
        this._dirty = true;
        const knopf = this.shadowRoot.querySelector('[data-act="save-scene"]');
        if (knopf) {
          knopf.removeAttribute("disabled");
          knopf.textContent = "Szene speichern";
        }
      }
      this._vorschau();
      return;
    }

    const slider = ev.target.closest("input[data-circuit]");
    if (!slider) return;
    const label = this.shadowRoot.querySelector(`[data-val="${slider.dataset.circuit}"]`);
    const value = Number(slider.value);
    if (label) label.textContent = value ? `${value} %` : "aus";
    if (this._editScene) {
      this._draft[slider.dataset.circuit] = value / 100;
      if (!this._dirty) {
        this._dirty = true;
        const button = this.shadowRoot.querySelector('[data-act="save-scene"]');
        if (button) {
          button.removeAttribute("disabled");
          button.textContent = "Szene speichern";
        }
      }
    }
  }

  async _onChange(ev) {
    const aus = ev.target.closest("input[data-aus]");
    if (aus) {
      const ausnahmen = { ...(this._draft.overrides || this._aktuelleOverrides()) };
      ausnahmen[aus.dataset.aus] = Math.min(100, Math.max(0, Number(aus.value))) / 100;
      this._draft = { ...this._draft, overrides: ausnahmen };
      this._dirty = true;
      this._vorschau();
      return this._render();
    }

    const dlgName = ev.target.closest('[data-dlg="name"]');
    if (dlgName) {
      await this._call("lichtregie/circuit/set", {
        zone_id: this._zoneId,
        circuit_id: this._dialog,
        name: dlgName.value,
      });
      this._config = await this._call("lichtregie/config/get");
      return this._render();
    }
    const dlgNum = ev.target.closest("[data-dlgnum]");
    if (dlgNum) {
      const zone = this.zoneConfig(this._zoneId);
      const circuit = (zone.circuits || []).find((c) => c.id === this._dialog);
      const f = (circuit.fixtures || [])[0];
      await this._call("lichtregie/fixture/set", {
        zone_id: this._zoneId,
        circuit_id: circuit.id,
        entity_id: f.entity_id,
        [dlgNum.dataset.dlgnum]: Math.min(100, Math.max(0, Number(dlgNum.value))) / 100,
      });
      this._config = await this._call("lichtregie/config/get");
      return this._render();
    }

    const lamp = ev.target.closest("[data-lamp],[data-lampnum]");
    if (lamp) {
      const id = lamp.dataset.lamp || lamp.dataset.lampnum;
      return this._saveLamp(id, lamp.dataset.field, lamp.value);
    }
    const mo = ev.target.closest("[data-mo]");
    if (mo) return this._saveMotion(Number(mo.dataset.mo), mo.dataset.field, mo.value);
    const ta = ev.target.closest("[data-ta]");
    if (ta) return this._saveKey(Number(ta.dataset.ta), ta.dataset.field, ta.value);

    const unit = ev.target.closest('[data-field="unit"]');
    if (unit) {
      this._controlId = unit.value;
      return this._render();
    }

    const field = ev.target.closest("[data-field]");
    if (field && field.dataset.field === "control_zone") {
      const control = this.controls.find((c) => c.id === this._controlId);
      if (control) {
        await this._call("lichtregie/control/set", {
          control: { ...control, zone_id: field.value || null },
        });
        this._config = await this._call("lichtregie/config/get");
        this._render();
      }
      return;
    }
    if (field && field.dataset.bind !== undefined) {
      return this._saveBinding(Number(field.dataset.bind), field.dataset.field, field.value);
    }

    const slider = ev.target.closest("input[data-circuit]");
    if (!slider) return;
    const levels = {};
    this.shadowRoot.querySelectorAll("input[data-circuit]").forEach((input) => {
      levels[input.dataset.circuit] = Number(input.value) / 100;
    });
    this._call("lichtregie/scene/preview", { zone_id: this._zoneId, levels });
  }
}

customElements.define("lichtregie-panel", LichtregiePanel);
