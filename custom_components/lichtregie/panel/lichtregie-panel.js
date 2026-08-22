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
  display:block; height:100%; background:var(--bg); color:var(--ink);
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
.body{display:grid;grid-template-columns:172px 1fr;min-height:calc(100% - 44px)}
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
@media(max-width:700px){
  .bind{grid-template-columns:1fr 1fr;}
  .bind.head{display:none}
  .body{grid-template-columns:1fr}
  nav{display:flex;overflow-x:auto;border-right:0;border-bottom:1px solid var(--line);padding:6px 4px}
  nav .grp{display:none}
  nav button{width:auto;white-space:nowrap;border-left:0;border-bottom:2px solid transparent;padding:7px 13px}
  nav button.on{border-left:0;border-bottom-color:var(--amber)}
}
`;

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
          ${this._navButton("zone", "Zone")}
          ${this._navButton("bedienung", "Bedienelemente")}
          <div class="grp">Service</div>
          ${this._navButton("tagesverlauf", "Tagesverlauf")}
          ${this._navButton("protokoll", "Protokoll")}
          ${this._navButton("anlage", "Anlage")}
        </nav>
        <main>${this._viewHtml()}</main>
      </div>`;

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
    return {
      leitstand: "Leitstand", bedienung: "Bedienelemente", protokoll: "Protokoll",
      anlage: "Anlage", tagesverlauf: "Tagesverlauf",
    }[this._view] || "";
  }

  _viewHtml() {
    if (this._error) return `<div class="empty">Die Lichtregie antwortet nicht: ${esc(this._error)}</div>`;
    if (!this._config) return `<div class="empty">Anlage wird geladen …</div>`;
    switch (this._view) {
      case "zone":
        return this._zoneHtml();
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
        "[data-edit],[data-delscene]"
    );
    if (!target) return;

    if (target.dataset.edit) {
      this._editScene = this._editScene === target.dataset.edit ? null : target.dataset.edit;
      this._dirty = false;
      this._draft = {};
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
          control_id: this._controlId,
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
      this._view = "zone";
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
      case "save-scene": {
        const zone = this.zoneConfig(this._zoneId);
        const scene = (zone.scenes || []).find((sc) => sc.id === this._editScene);
        if (!scene) return;
        const steps = Object.entries(this._draft)
          .filter(([, level]) => level > 0)
          .map(([circuit_id, level]) => {
            const old = (scene.steps || []).find((st) => st.circuit_id === circuit_id);
            return { circuit_id, level, kelvin: old ? old.kelvin : null };
          });
        await this._call("lichtregie/scene/set", {
          zone_id: this._zoneId,
          scene: { ...scene, steps },
        });
        this._config = await this._call("lichtregie/config/get");
        this._dirty = false;
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
        const steps = Object.entries(snapshot.levels || {})
          .filter(([, level]) => level > 0)
          .map(([circuit_id, level]) => ({
            circuit_id,
            level,
            kelvin: (snapshot.kelvin || {})[circuit_id] || null,
          }));
        const answer = await this._call("lichtregie/scene/set", {
          zone_id: this._zoneId,
          scene: { id: "", name, steps, fade: 1.5 },
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
        this._draft = snapshot.levels || {};
        this._dirty = !!this._editScene;
        this._busy = this._editScene
          ? "Ist-Zustand übernommen — noch nicht gespeichert."
          : "Ist-Zustand gelesen. Zum Sichern eine Szene bearbeiten.";
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

  _onInput(ev) {
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
