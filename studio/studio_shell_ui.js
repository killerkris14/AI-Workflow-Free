/* STUDIO_SHELL_V1 (AI Modeling Studio 0.016) + PROMPT_BUILDER_SYNC_V1 (0.017): header, page tabs (Prompt Builder | Image to 3D | .3mf Repair | Old Blender),
   status bundle next to Power, and draft memory. Pages are only hidden/shown - nothing is rebuilt, so typed text stays. */
(()=>{'use strict';
const $=id=>document.getElementById(id);
const make=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
if($('studio-shell-css'))return;
const css=make('style');css.id='studio-shell-css';css.textContent=`
html body .studio-hidden.studio-hidden.studio-hidden.studio-hidden{display:none!important}
header.studio-shell{display:grid!important;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:14px}
header.studio-shell>.studio-title{min-width:0}header.studio-shell>.studio-title p{margin:0}
#studio-tabs{display:flex;gap:6px;justify-content:center;padding:4px;border:1px solid #3d6a5c;border-radius:11px;background:#102b2466}
#studio-tabs button{font-size:15px;padding:9px 18px;border-radius:8px;white-space:nowrap}
#studio-tabs button.primary{background:#246c54;border-color:#7bc9a6;font-weight:700}
#studio-right{display:flex;align-items:center;justify-content:flex-end;gap:8px;min-width:0}
#studio-status-bundle{display:flex;align-items:center;gap:6px;flex-wrap:nowrap;min-width:0}
#studio-status-bundle #studio-version{margin:0!important}
header.studio-shell .portal-header-tools:empty{display:none}
.studio-page{margin-top:14px}
@media(max-width:1100px){header.studio-shell{grid-template-columns:minmax(0,1fr)}#studio-tabs{justify-content:flex-start;flex-wrap:wrap}#studio-right{justify-content:flex-start}}
/* Prompt Builder */
#page-prompt-builder .pb-grid{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,6fr);gap:18px;align-items:start}
@media(max-width:900px){#page-prompt-builder .pb-grid{grid-template-columns:minmax(0,1fr)}}
#page-prompt-builder fieldset{border:0;border-top:1px solid var(--line);margin:0;padding:12px 0 0;display:grid;gap:12px;min-width:0}
#page-prompt-builder fieldset:first-of-type{border-top:0;padding-top:0}
#page-prompt-builder legend{font-weight:800;padding:0 8px 0 0}
#page-prompt-builder .pb-field{display:grid;gap:5px;min-width:0}
#page-prompt-builder label{font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
#page-prompt-builder .pb-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
#page-prompt-builder textarea,#page-prompt-builder select,#page-prompt-builder input{width:100%;box-sizing:border-box;color:var(--ink);background:#0e1a2b;border:1px solid #506481;border-radius:7px;padding:8px 10px}
#pb-creature{min-height:110px}#pb-prompt{min-height:520px;font:12px/1.55 Consolas,'Courier New',monospace;white-space:pre-wrap}
#page-prompt-builder .pb-hint{font-size:12px;color:var(--muted);margin:0}#page-prompt-builder .pb-hint.warn{color:#ffcf6e}
#page-prompt-builder .pb-out{position:sticky;top:12px}#pb-status{min-height:1.3em;color:#81e3a5;font-size:13px}
#pb-diagram{display:grid;gap:6px;max-width:220px;grid-template-columns:repeat(2,1fr)}#pb-diagram.r4{grid-template-columns:repeat(4,1fr);max-width:360px}#pb-diagram.r5{grid-template-columns:repeat(5,1fr);max-width:420px}#pb-diagram.g32{grid-template-columns:repeat(6,1fr);max-width:300px}#pb-diagram.g32 div{grid-column:span 2}#pb-diagram.g32 div:nth-child(4){grid-column:2/span 2}
#page-prompt-builder .pb-lbl{font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
#page-prompt-builder select:disabled{opacity:.5}#page-prompt-builder #pb-presetSearch{margin-bottom:2px}
#pb-diagram div{border:1px dashed var(--line);border-radius:4px;aspect-ratio:1;display:grid;place-items:center;font:11px/1.25 Consolas,monospace;color:var(--muted);text-align:center;padding:4px}
#pb-diagram b{display:block;color:var(--ink);font-weight:600}
#pb-copy{font-weight:800;font-size:15px;padding:10px 22px}
/* .3mf Repair placeholder: a collage of home-made 404 "memes" */
#page-3mf-repair{position:relative;min-height:calc(100vh - 170px);overflow:hidden;border:1px solid var(--line);border-radius:12px;background:#10141c}
#page-3mf-repair .r404-wall{position:absolute;inset:0;pointer-events:none}
#page-3mf-repair .r404{position:absolute;font:900 22px/1.05 Impact,'Arial Black',sans-serif;color:#fff;text-transform:uppercase;letter-spacing:1px;
 -webkit-text-stroke:1.5px #000;text-shadow:2px 2px 0 #000;opacity:.55;white-space:nowrap;padding:10px 14px;border-radius:8px}
#page-3mf-repair .r404 small{display:block;font-size:12px;-webkit-text-stroke:0;text-shadow:none;opacity:.85}
#page-3mf-repair .r404.big{font-size:120px;opacity:.12;-webkit-text-stroke:3px #fff;color:transparent}
#page-3mf-repair .r404.tile{border:3px solid #fff;background:#0008}
#page-3mf-repair .r404.glitch{color:#ff3d7f;text-shadow:3px 0 #00e5ff,-3px 0 #ffe600}
#page-3mf-repair .r404.term{font:600 16px/1.3 Consolas,monospace;-webkit-text-stroke:0;text-shadow:none;color:#5dff8b;background:#000c;border:1px solid #5dff8b;text-transform:none}
#page-3mf-repair .r404-note{position:relative;z-index:1;max-width:560px;margin:18vh auto 0;padding:20px 24px;border:2px solid #86d7b1;border-radius:12px;background:#0d201de8;box-shadow:0 10px 40px #000a;font-size:17px;line-height:1.5}
#page-3mf-repair .r404-note h2{font-size:22px;margin:0 0 8px}
`;document.head.append(css);

// ---------- header ----------
const header=document.querySelector('main > header')||document.querySelector('header');
function arrangeHeader(){
 if(!header)return false;
 header.classList.add('studio-shell');
 const title=header.querySelector(':scope > div:first-child');if(title){title.classList.add('studio-title');const p=title.querySelector('p');if(p&&p.textContent!=='Killerkris14 Made it')p.textContent='Killerkris14 Made it';}
 let center=$('studio-tabs');
 const portalTabs=document.querySelector('.portal-workflow-switch');
 if(!center&&portalTabs){center=make('div');center.id='studio-tabs';center.setAttribute('role','tablist');}
 let right=$('studio-right');if(!right){right=make('div');right.id='studio-right';}
 let bundle=$('studio-status-bundle');if(!bundle){bundle=make('div');bundle.id='studio-status-bundle';right.append(bundle);}
 if(center&&center.parentElement!==header)header.insertBefore(center,title?title.nextSibling:header.firstChild);
 if(right.parentElement!==header)header.append(right);
 const conn=$('connection'),ver=$('studio-version'),power=$('studio-power-menu');
 if(conn&&conn.parentElement!==bundle)bundle.prepend(conn);
 if(ver&&ver.parentElement!==bundle)bundle.append(ver);else if(ver&&conn&&ver.previousElementSibling!==conn)conn.after(ver);
 if(power&&power.parentElement!==right)right.append(power);
 return !!(center&&portalTabs&&conn&&ver&&power);
}

// ---------- tabs ----------
const workspace=()=>document.querySelector('main .workspace');
const pages={};
function page(id){let p=$(id);if(!p){p=make('section',undefined,'studio-page');p.id=id;p.hidden=true;const anchor=document.querySelector('main .stats')||workspace();if(anchor)anchor.before(p);else document.querySelector('main').append(p);}pages[id]=p;return p;}
let built=false,current='';
function show(name){
 current=name;try{sessionStorage.setItem('studio-tab',name);}catch(e){}
 const own={'prompt':'page-prompt-builder','repair':'page-3mf-repair'}[name];
 for(const [id,p] of Object.entries(pages)){p.hidden=id!==own;p.classList.toggle('studio-hidden',id!==own);}
 const ws=workspace(),st=document.querySelector('main .stats');if(ws)ws.classList.toggle('studio-hidden',!!own);if(st)st.classList.toggle('studio-hidden',!!own);
 for(const b of document.querySelectorAll('#studio-tabs button'))b.classList.toggle('primary',b.dataset.tab===name);
}
function buildTabs(){
 const portalTabs=document.querySelector('.portal-workflow-switch'),center=$('studio-tabs');if(!portalTabs||!center)return false;
 const [hy,legacy]=Array.from(portalTabs.querySelectorAll('button'));if(!hy||!legacy)return false;
 if(built)return true;built=true;
 hy.dataset.tab='image';legacy.dataset.tab='legacy';legacy.textContent='Old Blender';
 const pb=make('button','Prompt Builder'),rp=make('button','.3mf Repair');pb.type=rp.type='button';pb.dataset.tab='prompt';rp.dataset.tab='repair';
 center.append(pb,hy,rp,legacy);portalTabs.remove();
 hy.addEventListener('click',()=>show('image'));legacy.addEventListener('click',()=>show('legacy'));
 pb.onclick=()=>show('prompt');rp.onclick=()=>show('repair');
 buildPromptBuilder(page('page-prompt-builder'));buildRepair(page('page-3mf-repair'));
 let saved='';try{saved=sessionStorage.getItem('studio-tab')||'';}catch(e){}
 if(saved==='legacy')legacy.click();else if(saved==='prompt'||saved==='repair')show(saved);else show('image');
 return true;
}

// ---------- draft memory: typed text survives tab switches AND page reloads (this browser tab only) ----------
function remember(root,prefix){
 if(!root||root.dataset.drafts)return;root.dataset.drafts='1';
 const fields=Array.from(root.querySelectorAll('textarea,input:not([type=file]):not([type=checkbox]):not([type=radio]):not([type=hidden]),select'));
 fields.forEach((f,i)=>{const key='studio-draft:'+prefix+':'+(f.id||i);
  try{const v=sessionStorage.getItem(key);if(v!==null&&f.value!==v){f.value=v;f.dispatchEvent(new Event('input',{bubbles:true}));}}catch(e){}
  const save=()=>{try{sessionStorage.setItem(key,f.value);}catch(e){}};f.addEventListener('input',save);f.addEventListener('change',save);});
}

// ---------- Prompt Builder: PROMPT_BUILDER_SYNC_V1 (0.017) - generated from the Turnaround Prompt Builder artifact
// (source sha256 d8affbd9df5c7ce3828d98818859e9150ac6b470e4f4978d2d49702ecbf8ddf3); rules in project doc tool-turnaround-prompt-builder.md. Do not hand-edit: re-sync from the artifact.
function buildPromptBuilder(root){
 if(root.dataset.built)return;root.dataset.built='1';root.classList.add('panel');
 root.innerHTML="<h2>Prompt Builder</h2><p class=\"muted small\">Pick a preset or describe any animal or creature, set its body, pose and look, and copy one prompt for your image generator. The prompt asks for a four-view orthographic sheet (front, left side, back, top) that AI Modeling Studio can turn into a model: the same pose in every view, flat colors and a white background. Then upload the sheet in <b>Image to 3D</b>.</p><p class=\"muted small\" style=\"margin-top:4px\">Prompt Builder build: Turnaround Prompt Builder artifact, synced 2026-10-30 (source sha256 d8affbd9df5c).</p><div class=\"pb-grid\"><form id=\"pb-form\" autocomplete=\"off\">\n      <fieldset>\n        <legend>Creature</legend>\n        <div class=\"pb-field\">\n          <label for=\"pb-presetSearch\">Find a preset</label>\n          <input type=\"search\" id=\"pb-presetSearch\" placeholder=\"Type to filter, e.g. zebra, owl, unicorn\">\n          <select id=\"pb-example\" aria-label=\"Preset\"></select>\n          <p class=\"pb-hint\" id=\"pb-presetHint\">Fills in the description, body type, wings, tail and base. Your proportions, style, outline and color choices stay as they are.</p>\n          <label for=\"pb-holiday\">Holiday theme</label>\n          <select id=\"pb-holiday\">\n            <option value=\"none\" selected>None</option>\n            <option value=\"newyear\">New Year's Day</option>\n            <option value=\"lunar\">Lunar New Year</option>\n            <option value=\"valentine\">Valentine's Day</option>\n            <option value=\"stpatrick\">St. Patrick's Day</option>\n            <option value=\"easter\">Easter</option>\n            <option value=\"eid\">Ramadan and Eid</option>\n            <option value=\"cinco\">Cinco de Mayo</option>\n            <option value=\"mother\">Mother's Day</option>\n            <option value=\"father\">Father's Day</option>\n            <option value=\"pride\">Pride Month</option>\n            <option value=\"juneteenth\">Juneteenth</option>\n            <option value=\"july4\">Independence Day</option>\n            <option value=\"rosh\">Rosh Hashanah</option>\n            <option value=\"diwali\">Diwali</option>\n            <option value=\"halloween\">Halloween</option>\n            <option value=\"dia\">D\u00eda de los Muertos</option>\n            <option value=\"thanksgiving\">Thanksgiving</option>\n            <option value=\"hanukkah\">Hanukkah</option>\n            <option value=\"christmas\">Christmas</option>\n            <option value=\"kwanzaa\">Kwanzaa</option>\n          </select>\n          <label for=\"pb-propSize\">Prop size</label>\n          <select id=\"pb-propSize\">\n            <option value=\"small\">Small props</option>\n            <option value=\"medium\" selected>Medium props</option>\n            <option value=\"large\">Large props</option>\n          </select>\n          <p class=\"pb-hint\">Changes how big the holiday props are and which props are used. Bigger props may cause color issues in the final file.</p>\n        </div>\n        <div class=\"pb-field\">\n          <label for=\"pb-creature\">Describe the creature</label>\n          <textarea id=\"pb-creature\" placeholder=\"e.g. a chubby baby dragon with red scales, a green belly and small brown antlers, wearing a red santa hat\">a chubby baby dragon with red scales, a light green belly, small brown antlers, big round eyes and short stubby legs</textarea>\n          <p class=\"pb-hint\">Shape, colors, markings, accessories, number of legs. Anything you add here goes into the prompt.</p>\n        </div>\n      </fieldset>\n\n      <fieldset>\n        <legend>Body and pose</legend>\n        <div class=\"pb-row\">\n          <div class=\"pb-field\">\n            <label for=\"pb-body\">Body type</label>\n            <select id=\"pb-body\">\n              <option value=\"four\" selected>Four legs, standing</option>\n              <option value=\"sit\">Four legs, sitting up</option>\n              <option value=\"belly\">Lying on its belly</option>\n              <option value=\"two\">Two legs, upright</option>\n              <option value=\"bird\">Bird</option>\n              <option value=\"many\">Many legs (insect, spider, crab)</option>\n              <option value=\"snake\">Snake / serpent / worm</option>\n              <option value=\"swim\">Fish / whale / sea creature</option>\n              <option value=\"tentacle\">Tentacles (octopus, jellyfish)</option>\n              <option value=\"blob\">Blob, no limbs</option>\n              <option value=\"custom\">Other (follow my description)</option>\n            </select>\n          </div>\n          <div class=\"pb-field\">\n            <label for=\"pb-proportions\">Proportions</label>\n            <select id=\"pb-proportions\">\n              <option value=\"chibi\" selected>Cute: big head, short limbs</option>\n              <option value=\"plush\">Plush toy: soft and stubby</option>\n              <option value=\"chubby\">Chubby and round</option>\n              <option value=\"baby\">Baby animal</option>\n              <option value=\"cartoon\">Cartoon, close to real</option>\n              <option value=\"natural\">Natural, like the real animal</option>\n              <option value=\"slender\">Tall and slender</option>\n              <option value=\"bulky\">Big, bulky and strong</option>\n              <option value=\"asis\">As described</option>\n            </select>\n          </div>\n        </div>\n        <div class=\"pb-row\">\n          <div class=\"pb-field\">\n            <label for=\"pb-wings\">Wings</label>\n            <select id=\"pb-wings\">\n              <option value=\"none\">No wings</option>\n              <option value=\"folded\" selected>Folded against the body</option>\n              <option value=\"flat\">Spread out flat, like gliding</option>\n              <option value=\"upright\">Raised upright behind</option>\n            </select>\n          </div>\n          <div class=\"pb-field\">\n            <label for=\"pb-tail\">Tail</label>\n            <select id=\"pb-tail\">\n              <option value=\"none\">No tail</option>\n              <option value=\"short\">Short stub</option>\n              <option value=\"feathers\">Short tail feathers</option>\n              <option value=\"long\" selected>Long, straight back on the ground</option>\n              <option value=\"hang\">Hanging down (horse, lion)</option>\n              <option value=\"up\">Long, curving up behind</option>\n              <option value=\"bushy\">Big bushy, raised (fox, squirrel)</option>\n              <option value=\"spiral\">Curled spiral (seahorse, chameleon)</option>\n              <option value=\"finv\">Upright fish fin</option>\n              <option value=\"flukes\">Flat whale flukes</option>\n              <option value=\"paddle\">Flat paddle (beaver)</option>\n              <option value=\"fan\">Fanned out (peacock, many tails)</option>\n            </select>\n          </div>\n        </div>\n        <div class=\"pb-field\">\n          <label for=\"pb-base\">Base</label>\n          <select id=\"pb-base\">\n            <option value=\"none\" selected>No base, stands on its own</option>\n            <option value=\"round\">Simple round base</option>\n            <option value=\"oval\">Simple oval base</option>\n          </select>\n          <p class=\"pb-hint\">A base helps creatures that don't stand well on their own: fish, birds, snakes, long-legged animals.</p>\n        </div>\n        <div id=\"pb-notes\"></div>\n      </fieldset>\n\n      <fieldset>\n        <legend>Look and sheet</legend>\n        <div class=\"pb-row\">\n          <div class=\"pb-field\">\n            <label for=\"pb-style\">Drawing style</label>\n            <select id=\"pb-style\">\n              <option value=\"flat\" selected>Flat cartoon (recommended)</option>\n              <option value=\"kawaii\">Kawaii sticker</option>\n              <option value=\"vinyl\">Vinyl toy figure</option>\n              <option value=\"clay\">Clay figure</option>\n              <option value=\"cel\">Anime, flat cel colors</option>\n              <option value=\"lowpoly\">Low-poly facets</option>\n              <option value=\"voxel\">Blocky voxel</option>\n              <option value=\"stylized\">Stylized, light detail</option>\n              <option value=\"storybook\">Storybook, soft shading</option>\n              <option value=\"realistic\">Realistic painted</option>\n            </select>\n          </div>\n          <div class=\"pb-field\">\n            <label for=\"pb-outlines\">Outlines</label>\n            <select id=\"pb-outlines\">\n              <option value=\"none\" selected>None (recommended)</option>\n              <option value=\"thin\">Thin black outlines</option>\n              <option value=\"thick\">Thick black outlines</option>\n            </select>\n          </div>\n        </div>\n        <div class=\"pb-row\">\n          <div class=\"pb-field\">\n            <label for=\"pb-colors\">Number of colors</label>\n            <select id=\"pb-colors\">\n              <option value=\"3\">3</option>\n              <option value=\"4\" selected>4 (default filaments)</option>\n              <option value=\"5\">5</option>\n              <option value=\"6\">6</option>\n              <option value=\"7\">7</option>\n              <option value=\"8\">8</option>\n              <option value=\"9\">9 (printer max)</option>\n            </select>\n          </div>\n          <div class=\"pb-field\">\n            <label for=\"pb-layout\">Sheet layout</label>\n            <select id=\"pb-layout\">\n              <option value=\"grid\" selected>2 \u00d7 2 grid (square)</option>\n              <option value=\"row\">4 in a row (wide)</option>\n              <option value=\"grid5\">3 on top, 2 below (adds bottom view)</option>\n            </select>\n          </div>\n        </div>\n        <div class=\"pb-field\">\n          <span class=\"pb-lbl\">Where each view goes</span>\n          <div class=\"panels g2\" id=\"pb-diagram\"></div>\n        </div>\n      </fieldset>\n    </form>\n<section class=\"pb-out\" aria-labelledby=\"pb-out-title\">\n      <div class=\"row between\" style=\"align-items:center\">\n        <h3 id=\"pb-out-title\" style=\"margin:0\">Your prompt</h3>\n        <button type=\"button\" class=\"primary\" id=\"pb-copy\">Copy prompt</button>\n      </div>\n      <div id=\"pb-status\" role=\"status\" aria-live=\"polite\"></div>\n      <textarea id=\"pb-prompt\" readonly aria-label=\"Generated prompt\"></textarea>\n    </section></div>";
 (function(){
  var $ = function (id) { return document.getElementById('pb-' + id); };
  var ids = ["creature", "body", "proportions", "wings", "tail", "base", "colors", "style", "outlines", "layout", "holiday", "propSize"];
  var KEY = "turnaround-prompt-v2";

  /* Presets: [label, body, wings, tail, base, description] */
  var GROUPS = [
    ["Fantasy and myth", [
      ["Unicorn", "four", "none", "hang", "oval", "a white unicorn with a flowing pastel rainbow mane and tail, a thick gold spiral horn and pink hooves"],
      ["Unicorn foal", "four", "none", "hang", "oval", "a chubby baby unicorn with pale pink fur, a lavender mane and tail, a short thick gold horn and big sparkly eyes"],
      ["Winged unicorn", "four", "folded", "hang", "oval", "a lavender winged unicorn with a thick silver spiral horn, a purple and blue mane and tail, and feathered pale blue wings"],
      ["Pegasus", "four", "folded", "hang", "oval", "a cream-colored winged horse with feathered pale gold wings, a golden mane and tail and gold hooves"],
      ["Narwhal unicorn (cartoon)", "swim", "none", "flukes", "oval", "a cute pastel blue narwhal with a pale belly, freckles on its cheeks and a thick spiral rainbow horn"],
      ["Baby dragon", "four", "folded", "long", "none", "a chubby baby dragon with red scales, a light green belly, small brown antlers, big round eyes and short stubby legs"],
      ["Adult dragon", "four", "folded", "long", "oval", "a large green dragon with a yellow belly, two curved horns, a row of back spikes and bat-like wings"],
      ["Wyvern", "two", "folded", "long", "oval", "a two-legged blue wyvern with large bat-like wings, a pale belly and an arrow-shaped tail tip"],
      ["Eastern dragon", "snake", "none", "none", "none", "a long red eastern dragon with a serpent body, four short legs, a golden belly, a flowing golden mane and short thick whiskers"],
      ["Fairy dragon", "four", "flat", "long", "round", "a tiny pastel green fairy dragon with pink butterfly-like wings and two short rounded antennae"],
      ["Griffin", "four", "folded", "hang", "oval", "a griffin with the head, front talons and wings of a golden eagle and the body, back legs and tufted tail of a lion"],
      ["Phoenix", "bird", "folded", "fan", "round", "a fiery phoenix bird with red, orange and yellow feathers and a fanned tail"],
      ["Hydra", "four", "none", "long", "oval", "a green three-headed hydra with three thick necks of equal length, a yellow belly and small back spikes"],
      ["Cerberus", "four", "none", "hang", "none", "a three-headed black guard dog with red eyes and a spiked red collar on each neck"],
      ["Nine-tailed fox", "four", "none", "fan", "none", "an orange nine-tailed fox spirit with a cream belly and red face markings; its nine bushy tails fan out upright behind it"],
      ["Jackalope", "sit", "none", "short", "none", "a brown jackalope rabbit with a cream belly and small antlers"],
      ["Kraken", "tentacle", "none", "none", "none", "a dark teal kraken with a round head, big yellow eyes and eight thick tentacles with pale suckers"],
      ["Sea serpent", "snake", "none", "none", "none", "a blue sea serpent with a pale belly and a fin running down its back"],
      ["Lake monster", "belly", "none", "long", "oval", "a friendly green long-necked lake monster with four flippers and a lighter belly"],
      ["Kaiju", "two", "none", "long", "none", "a chubby green kaiju lizard monster with jagged gray back plates and a lighter belly"],
      ["Yeti", "two", "none", "none", "none", "a fluffy white yeti with a blue face, hands and feet, two small horns and a big grin"],
      ["Bigfoot", "two", "none", "none", "none", "a tall brown bigfoot with shaggy fur, a lighter face and big feet"],
      ["Slime blob", "blob", "none", "none", "none", "a round green slime blob with big eyes and a small smile"]
    ]],
    ["Dinosaurs and prehistoric", [
      ["T. rex", "two", "none", "long", "none", "a green T. rex with tiny arms, a big head, a lighter belly and dark stripes on its back"],
      ["Triceratops", "four", "none", "long", "none", "an orange triceratops with a big bony frill, three thick horns and a beige beak"],
      ["Stegosaurus", "four", "none", "long", "none", "a green stegosaurus with two rows of big orange back plates and four thick tail spikes"],
      ["Brachiosaurus", "four", "none", "long", "oval", "a blue-green long-necked brachiosaurus with a pale belly"],
      ["Velociraptor", "two", "none", "long", "oval", "a brown velociraptor with feathered arms, dark stripes and a curved toe claw"],
      ["Ankylosaurus", "four", "none", "long", "none", "a tan ankylosaurus with an armored back, side spikes and a club at the tip of its tail"],
      ["Spinosaurus", "two", "none", "long", "oval", "a gray-green spinosaurus with a tall red sail on its back and a long crocodile-like snout"],
      ["Parasaurolophus", "four", "none", "long", "none", "a yellow parasaurolophus with a long curved head crest and brown stripes"],
      ["Pterodactyl", "two", "flat", "short", "round", "a reddish pterodactyl with a long crested head and wide leathery wings"],
      ["Woolly mammoth", "four", "none", "short", "none", "a woolly mammoth with shaggy brown fur, small ears and long curved thick tusks"],
      ["Saber-toothed cat", "four", "none", "short", "none", "a tan saber-toothed cat with two long thick fangs and a short tail"]
    ]],
    ["Zoo: Africa", [
      ["Lion", "four", "none", "hang", "none", "a male lion with golden fur, a big dark orange mane and a dark tuft at the tail tip"],
      ["Lioness", "four", "none", "hang", "none", "a lioness with sandy golden fur, a cream muzzle and belly and a dark tail tuft"],
      ["Lion cub", "sit", "none", "hang", "none", "a fluffy lion cub with golden fur, faint spots on its legs and big round eyes"],
      ["Cheetah", "four", "none", "long", "none", "a slender cheetah with golden fur, black spots and black tear lines on its face"],
      ["Leopard", "four", "none", "long", "none", "a leopard with golden fur and black rosette spots"],
      ["Zebra", "four", "none", "hang", "oval", "a zebra with bold black and white stripes, a short upright striped mane and a black muzzle"],
      ["Giraffe", "four", "none", "hang", "oval", "a giraffe with a long thick neck, tan fur with brown patches and two short ossicone horns"],
      ["Elephant", "four", "none", "short", "none", "a gray African elephant with big ears, a thick trunk and short thick tusks"],
      ["Baby elephant", "four", "none", "short", "none", "a chubby baby elephant with gray skin, big floppy ears and a short trunk"],
      ["Rhinoceros", "four", "none", "short", "none", "a gray rhinoceros with two thick horns on its nose and folds of armored skin"],
      ["Hippopotamus", "four", "none", "short", "none", "a round purple-gray hippopotamus with a pink belly, small ears and a wide mouth"],
      ["Warthog", "four", "none", "short", "none", "a brown warthog with curved tusks, a bristly mane and bumps on its face"],
      ["Meerkat", "two", "none", "long", "none", "a meerkat standing upright on its back legs, tan fur, dark eye patches, its tail resting on the ground behind it"],
      ["Hyena", "four", "none", "hang", "none", "a spotted hyena with sandy fur, dark spots and round ears"],
      ["Gazelle", "four", "none", "short", "oval", "a gazelle with tan fur, a cream belly, a dark side stripe and two curved ridged horns"],
      ["Wildebeest", "four", "none", "hang", "oval", "a gray-brown wildebeest with curved horns, a dark beard and mane"],
      ["Okapi", "four", "none", "hang", "oval", "an okapi with dark brown fur, zebra-striped back legs and a pale face"],
      ["African wild dog", "four", "none", "hang", "none", "an African wild dog with patchy brown, black and tan fur and big round ears"],
      ["Gorilla", "four", "none", "none", "none", "a big black gorilla with a silver back, standing on all fours on its knuckles"],
      ["Chimpanzee", "sit", "none", "none", "none", "a chimpanzee with dark brown fur and a light tan face, ears and hands"],
      ["Baboon", "four", "none", "hang", "none", "an olive-brown baboon with a long dog-like muzzle"],
      ["Mandrill", "sit", "none", "short", "none", "a mandrill with olive fur, a red nose stripe and blue ridges on its face"],
      ["Ring-tailed lemur", "sit", "none", "up", "none", "a ring-tailed lemur with gray fur, a white face mask, orange eyes and a black and white ringed tail"],
      ["Ostrich", "bird", "folded", "feathers", "oval", "an ostrich with black body feathers, white wing tips, a long pink neck and thick pink legs"],
      ["Camel", "four", "none", "hang", "oval", "a tan dromedary camel with one hump and long legs"],
      ["Aardvark", "four", "none", "long", "none", "a pinkish-tan aardvark with a long snout, long ears and a thick tail"]
    ]],
    ["Zoo: big cats and bears", [
      ["Tiger", "four", "none", "long", "none", "an orange tiger with black stripes and a cream belly and muzzle"],
      ["White tiger", "four", "none", "long", "none", "a white tiger with black stripes and blue eyes"],
      ["Snow leopard", "four", "none", "long", "none", "a pale gray snow leopard with dark rosette spots and a very thick long tail"],
      ["Jaguar", "four", "none", "long", "none", "a stocky jaguar with golden fur and large black rosettes"],
      ["Black panther", "four", "none", "long", "none", "a sleek black panther with yellow-green eyes"],
      ["Cougar", "four", "none", "long", "none", "a tan cougar with a cream muzzle and a dark tail tip"],
      ["Brown bear", "four", "none", "short", "none", "a big brown grizzly bear with a shoulder hump and light brown muzzle"],
      ["Polar bear", "four", "none", "short", "none", "a polar bear with cream-white fur, a black nose and small round ears"],
      ["Black bear", "four", "none", "short", "none", "a black bear with a tan muzzle"],
      ["Giant panda", "sit", "none", "short", "none", "a giant panda with white fur, black legs, shoulders, ears and eye patches"],
      ["Red panda", "four", "none", "bushy", "none", "a red panda with rusty red fur, white face markings, black legs and a ringed bushy tail"],
      ["Koala", "sit", "none", "none", "none", "a gray koala with big fluffy ears and a large black nose"]
    ]],
    ["Zoo: Asia and the Americas", [
      ["Orangutan", "sit", "none", "none", "none", "an orangutan with long shaggy orange fur and wide cheek pads"],
      ["Spider monkey", "sit", "none", "spiral", "none", "a brown spider monkey with long arms and a tail that curls into a spiral behind it"],
      ["Capuchin monkey", "sit", "none", "spiral", "none", "a capuchin monkey with a black cap, cream face and chest and brown body"],
      ["Tapir", "four", "none", "short", "none", "a Malayan tapir with a black front and back and a white middle, and a short trunk"],
      ["Yak", "four", "none", "hang", "none", "a shaggy dark brown yak with long fur and curved horns"],
      ["Pangolin", "four", "none", "long", "none", "a brown pangolin covered in overlapping armor scales"],
      ["Bison", "four", "none", "hang", "none", "an American bison with a shaggy dark brown hump and head and short curved horns"],
      ["Moose", "four", "none", "short", "oval", "a dark brown moose with wide flat antlers and a beard under its chin"],
      ["Elk", "four", "none", "short", "oval", "a brown elk with a darker neck, a cream rump and big branching antlers"],
      ["Reindeer", "four", "none", "short", "oval", "a reindeer with brown fur, a cream neck ruff and large branching antlers"],
      ["Deer fawn", "four", "none", "short", "oval", "a baby deer fawn with reddish fur and white spots on its back"],
      ["Llama", "four", "none", "short", "oval", "a fluffy cream llama with long banana-shaped ears"],
      ["Alpaca", "four", "none", "short", "oval", "a fluffy brown alpaca with a round fluffy head"],
      ["Gray wolf", "four", "none", "hang", "none", "a gray wolf with a cream belly and muzzle and yellow eyes"],
      ["Red fox", "four", "none", "bushy", "none", "a red fox with a cream chest, black legs and a bushy tail with a cream tip"],
      ["Arctic fox", "four", "none", "bushy", "none", "an arctic fox with fluffy white fur, a black nose and small round ears"],
      ["Raccoon", "four", "none", "long", "none", "a gray raccoon with a black eye mask and a ringed bushy tail"],
      ["Skunk", "four", "none", "bushy", "none", "a black skunk with a white stripe down its back and a big bushy tail"],
      ["Beaver", "four", "none", "paddle", "none", "a brown beaver with big orange front teeth and a flat dark tail"],
      ["River otter", "four", "none", "long", "none", "a brown river otter with a cream chest and a thick tapered tail"],
      ["Sea otter", "sit", "none", "short", "none", "a sea otter with brown fur, a cream face and whisker pads, holding its paws together"],
      ["Sloth", "sit", "none", "none", "none", "a smiling three-toed sloth with shaggy tan fur and dark eye stripes"],
      ["Armadillo", "four", "none", "long", "none", "a gray-tan armadillo with banded shell armor"],
      ["Giant anteater", "four", "none", "bushy", "none", "a giant anteater with a long thin snout, gray-brown fur, a black and white shoulder stripe and a bushy tail"],
      ["Capybara", "four", "none", "none", "none", "a round brown capybara with a blunt square snout"],
      ["Porcupine", "four", "none", "short", "none", "a brown porcupine with short thick cream-tipped quills"],
      ["Opossum", "four", "none", "long", "none", "a gray opossum with a pale face, pink nose and a thick pink tail"],
      ["Prairie dog", "two", "none", "short", "none", "a tan prairie dog standing upright with its paws together"],
      ["Mountain goat", "four", "none", "short", "oval", "a shaggy cream mountain goat with short black horns and a beard"],
      ["Bighorn sheep", "four", "none", "short", "oval", "a brown bighorn sheep with large curled horns and a cream muzzle and rump"]
    ]],
    ["Zoo: Australia", [
      ["Kangaroo", "two", "none", "long", "none", "a red-brown kangaroo standing on its big back feet with its thick tail resting on the ground"],
      ["Wombat", "four", "none", "short", "none", "a chunky brown wombat with a round nose and small ears"],
      ["Platypus", "four", "none", "paddle", "none", "a brown platypus with a flat dark duck bill, webbed feet and a flat tail"],
      ["Tasmanian devil", "four", "none", "long", "none", "a black Tasmanian devil with a white chest band and pink ears"],
      ["Echidna", "four", "none", "short", "none", "a brown echidna with short thick cream spines and a long snout"],
      ["Emu", "bird", "folded", "feathers", "oval", "a shaggy brown emu with a blue-gray neck and thick legs"],
      ["Kookaburra", "bird", "folded", "feathers", "round", "a kookaburra with a cream head, brown eye stripe, brown wings and a big beak"]
    ]],
    ["Ocean", [
      ["Narwhal (sea unicorn)", "swim", "none", "flukes", "oval", "a mottled gray narwhal with a pale belly and one long thick spiral tusk"],
      ["Dolphin", "swim", "none", "flukes", "oval", "a smiling gray bottlenose dolphin with a pale belly"],
      ["Orca", "swim", "none", "flukes", "oval", "an orca with a black body, white belly, white eye patches and a tall dorsal fin"],
      ["Humpback whale", "swim", "none", "flukes", "oval", "a dark blue-gray humpback whale with long flippers and a pale grooved throat"],
      ["Blue whale", "swim", "none", "flukes", "oval", "a long blue-gray blue whale with a pale belly and small dorsal fin"],
      ["Beluga whale", "swim", "none", "flukes", "oval", "a white beluga whale with a rounded forehead and a smile"],
      ["Sperm whale", "swim", "none", "flukes", "oval", "a dark gray sperm whale with a huge square head"],
      ["Shark", "swim", "none", "finv", "oval", "a friendly gray shark with a white belly, a big dorsal fin and a small smile"],
      ["Hammerhead shark", "swim", "none", "finv", "oval", "a gray hammerhead shark with a wide hammer-shaped head and white belly"],
      ["Whale shark", "swim", "none", "finv", "oval", "a dark blue whale shark with white spots and stripes and a wide mouth"],
      ["Manta ray", "swim", "none", "short", "oval", "a manta ray with a black back, white underside and wide flat wing-like fins"],
      ["Sea turtle", "swim", "none", "short", "oval", "a green sea turtle with a brown patterned shell and four flippers"],
      ["Seal", "belly", "none", "short", "none", "a gray harbor seal with dark spots and big black eyes"],
      ["Sea lion", "sit", "none", "short", "none", "a brown sea lion sitting up on its front flippers"],
      ["Walrus", "belly", "none", "short", "none", "a brown walrus with long thick tusks and a bristly mustache"],
      ["Manatee", "belly", "none", "paddle", "none", "a gray manatee with a round paddle tail and small flippers"],
      ["Penguin", "bird", "folded", "short", "none", "an emperor penguin with a black back, white belly and yellow-orange neck patches"],
      ["Penguin chick", "bird", "folded", "short", "none", "a fluffy gray penguin chick with a black head and white face"],
      ["Octopus", "tentacle", "none", "none", "none", "a purple octopus with a round head, big friendly eyes and eight thick curling tentacles with pink suckers"],
      ["Squid", "tentacle", "none", "none", "none", "a red squid with a pointed head fin, big eyes and ten thick tentacles"],
      ["Jellyfish", "tentacle", "none", "none", "none", "a pink jellyfish with a round bell-shaped body and thick ribbon tentacles resting on the ground"],
      ["Seahorse", "custom", "none", "spiral", "round", "an orange seahorse standing upright with a curled tail and a small back fin"],
      ["Clownfish", "swim", "none", "finv", "round", "an orange clownfish with three white bands edged in black"],
      ["Pufferfish", "swim", "none", "finv", "round", "a round yellow pufferfish with short thick spikes and big eyes"],
      ["Starfish", "custom", "none", "none", "none", "a five-armed orange starfish lying flat on the ground with bumpy dots"],
      ["Crab", "many", "none", "none", "none", "a red crab with two big claws, six walking legs and eyes on short stalks"],
      ["Lobster", "many", "none", "paddle", "none", "a red lobster with two big claws, long antennae laid back along the body and a fan tail"],
      ["Hermit crab", "many", "none", "none", "none", "an orange hermit crab peeking out of a spiral seashell"]
    ]],
    ["Birds", [
      ["Owl", "bird", "folded", "short", "round", "a fluffy brown barn owl with a cream heart-shaped face, big black eyes and an orange beak"],
      ["Snowy owl", "bird", "folded", "short", "round", "a snowy owl with white feathers, black speckles and yellow eyes"],
      ["Bald eagle", "bird", "folded", "feathers", "round", "a bald eagle with a dark brown body, white head and tail and a yellow beak"],
      ["Macaw", "bird", "folded", "long", "round", "a scarlet macaw with red, yellow and blue feathers and long tail feathers"],
      ["Toucan", "bird", "folded", "feathers", "round", "a black toucan with a white throat and a huge orange and yellow beak"],
      ["Cockatoo", "bird", "folded", "feathers", "round", "a white cockatoo with a raised yellow crest"],
      ["Peacock", "bird", "folded", "fan", "oval", "a blue peacock with a green fanned tail covered in eye spots"],
      ["Flamingo", "bird", "folded", "feathers", "round", "a pink flamingo standing on two thick legs, with a curved neck and a black-tipped beak"],
      ["Pelican", "bird", "folded", "feathers", "round", "a white pelican with a big orange throat pouch"],
      ["Puffin", "bird", "folded", "short", "round", "an Atlantic puffin with a black back, white face and belly and a striped orange beak"],
      ["Swan", "belly", "folded", "feathers", "oval", "a white swan resting on the ground with a curved neck and orange beak"],
      ["Duck", "bird", "folded", "feathers", "none", "a mallard duck with a green head, yellow bill and brown chest"],
      ["Duckling", "bird", "folded", "short", "none", "a fluffy yellow duckling with an orange bill and feet"],
      ["Chicken", "bird", "folded", "up", "none", "a brown hen with a red comb and wattle"],
      ["Rooster", "bird", "folded", "up", "none", "a rooster with red-orange feathers, a big red comb and a dark green arched tail"],
      ["Hummingbird", "bird", "flat", "feathers", "round", "a green hummingbird with a red throat and a long thin beak"],
      ["Kiwi", "bird", "none", "none", "none", "a round brown kiwi bird with a long thin beak"],
      ["Raven", "bird", "folded", "feathers", "round", "a glossy black raven with a thick beak"],
      ["Robin", "bird", "folded", "feathers", "round", "a round robin with a brown back and orange-red chest"],
      ["Parakeet", "bird", "folded", "long", "round", "a green and yellow budgie parakeet with black wave markings"]
    ]],
    ["Reptiles and amphibians", [
      ["Crocodile", "four", "none", "long", "none", "a green crocodile with a long toothy snout, bumpy back armor and a pale belly"],
      ["Alligator", "four", "none", "long", "none", "a dark green alligator with a wide rounded snout and bumpy back"],
      ["Komodo dragon", "four", "none", "long", "none", "a gray-brown Komodo dragon with a long forked tongue tucked in"],
      ["Iguana", "four", "none", "long", "none", "a green iguana with a spiky back crest and a striped tail"],
      ["Chameleon", "four", "none", "spiral", "oval", "a green chameleon with a casque head, turret eyes and a spiral tail"],
      ["Gecko", "four", "none", "long", "none", "a yellow leopard gecko with brown spots and big eyes"],
      ["Bearded dragon", "four", "none", "long", "none", "a tan bearded dragon with a spiky beard and side spikes"],
      ["Tortoise", "four", "none", "short", "none", "a tortoise with a high brown domed shell and thick gray legs"],
      ["Turtle", "four", "none", "short", "none", "a green turtle with a patterned shell"],
      ["Cobra", "snake", "none", "none", "none", "a brown cobra with its hood spread and head raised, with a cream belly"],
      ["Python", "snake", "none", "none", "none", "a ball python with brown and tan blotches"],
      ["Snake", "snake", "none", "none", "none", "a green snake with yellow diamond markings on its back and a pale yellow belly"],
      ["Frog", "sit", "none", "none", "none", "a bright green tree frog with a yellow belly, big orange eyes and orange toe pads"],
      ["Toad", "sit", "none", "none", "none", "a bumpy brown toad with a cream belly"],
      ["Poison dart frog", "sit", "none", "none", "none", "a blue poison dart frog with black spots"],
      ["Axolotl", "four", "none", "long", "none", "a pink axolotl with feathery gill fronds and a smile"],
      ["Salamander", "four", "none", "long", "none", "a black salamander with yellow spots"]
    ]],
    ["Bugs and small critters", [
      ["Ladybug", "many", "folded", "none", "none", "a red ladybug with black spots, a black head and six short legs"],
      ["Bumblebee", "many", "flat", "none", "round", "a fuzzy yellow and black bumblebee with small clear wings"],
      ["Butterfly", "many", "flat", "none", "round", "a monarch butterfly with orange wings, black veins and white dots"],
      ["Dragonfly", "many", "flat", "long", "round", "a blue dragonfly with four long wings and a long thin body"],
      ["Stag beetle", "many", "folded", "none", "none", "a dark brown stag beetle with big antler-like jaws"],
      ["Rhinoceros beetle", "many", "folded", "none", "none", "a shiny black rhinoceros beetle with a big curved horn"],
      ["Ant", "many", "none", "none", "none", "a red ant with three body segments and six legs"],
      ["Spider", "many", "none", "none", "none", "a fuzzy black jumping spider with eight thick legs, big shiny eyes and a red spot on its back"],
      ["Tarantula", "many", "none", "none", "none", "a hairy brown tarantula with orange-banded legs"],
      ["Scorpion", "many", "none", "up", "none", "a black scorpion with two claws and a segmented tail curving up over its back"],
      ["Praying mantis", "many", "folded", "none", "round", "a green praying mantis with folded front legs and a triangular head"],
      ["Grasshopper", "many", "folded", "none", "none", "a green grasshopper with big back legs"],
      ["Snail", "custom", "none", "none", "none", "a snail with a pale tan body and a brown spiral shell"],
      ["Caterpillar", "snake", "none", "none", "none", "a chubby green caterpillar with yellow spots and many short legs"],
      ["Hedgehog", "four", "none", "none", "none", "a round hedgehog with brown spines and a cream face"]
    ]],
    ["Farm and pets", [
      ["House cat", "four", "none", "up", "none", "a round orange tabby house cat with white paws, a white chest, green eyes and pointed ears"],
      ["Kitten", "sit", "none", "up", "none", "a gray tabby kitten with big blue eyes"],
      ["Puppy", "four", "none", "short", "none", "a happy golden retriever puppy with floppy ears, a black nose and a red collar"],
      ["Corgi", "four", "none", "short", "none", "an orange and white corgi with short legs and big pointed ears"],
      ["Dachshund", "four", "none", "long", "none", "a brown dachshund with a long body and short legs"],
      ["Pug", "sit", "none", "short", "none", "a fawn pug with a black wrinkled face and curly tail"],
      ["Husky", "four", "none", "bushy", "none", "a gray and white husky with blue eyes and a curled bushy tail"],
      ["Dalmatian", "four", "none", "long", "none", "a white Dalmatian with black spots"],
      ["Bunny", "sit", "none", "short", "none", "a brown bunny with long upright ears and a cream fluffy tail"],
      ["Guinea pig", "four", "none", "none", "none", "a tan and white guinea pig"],
      ["Hamster", "sit", "none", "none", "none", "a golden hamster with chubby cheeks and a cream belly"],
      ["Ferret", "four", "none", "long", "none", "a cream ferret with a dark mask and legs"],
      ["Goldfish", "swim", "none", "finv", "round", "an orange goldfish with a flowing tail fin"],
      ["Horse", "four", "none", "hang", "oval", "a brown horse with a black mane and tail, white socks on all four legs and a white blaze on the face"],
      ["Pony", "four", "none", "hang", "none", "a chubby gray pony with a long mane and tail"],
      ["Donkey", "four", "none", "hang", "none", "a gray donkey with long ears and a pale muzzle"],
      ["Cow", "four", "none", "hang", "none", "a black and white dairy cow with a pink nose and udder"],
      ["Highland cow", "four", "none", "hang", "none", "a shaggy ginger highland cow with long curved horns and fur over its eyes"],
      ["Pig", "four", "none", "short", "none", "a pink pig with a round snout and floppy ears"],
      ["Sheep", "four", "none", "short", "none", "a fluffy cream sheep with a black face and legs"],
      ["Goat", "four", "none", "short", "none", "a brown and white goat with small horns and a beard"]
    ]]
  ];

  var PRESETS = {};
  var total = 0;
  function fillPresets(filter) {
    var sel = $("example");
    var q = (filter || "").trim().toLowerCase();
    var html = '<option value="">' + (q ? "Matching presets…" : "Choose a preset…") + "</option>";
    var shown = 0;
    GROUPS.forEach(function (g, gi) {
      var items = g[1].map(function (p, pi) { return { p: p, k: gi + "-" + pi }; })
        .filter(function (x) { return !q || x.p[0].toLowerCase().indexOf(q) >= 0 || x.p[5].toLowerCase().indexOf(q) >= 0 || g[0].toLowerCase().indexOf(q) >= 0; });
      if (!items.length) return;
      html += '<optgroup label="' + g[0] + '">';
      items.forEach(function (x) { html += '<option value="' + x.k + '">' + x.p[0] + "</option>"; shown++; });
      html += "</optgroup>";
    });
    sel.innerHTML = html;
    $("presetHint").textContent = q
      ? shown + " of " + total + " presets match."
      : total + " presets. Picking one fills in the description, body type, wings, tail and base. Your proportions, style, outline and color choices stay as they are.";
  }
  GROUPS.forEach(function (g, gi) { g[1].forEach(function (p, pi) { PRESETS[gi + "-" + pi] = p; total++; }); });

  /* [label, small, medium, large] */
  var HOLIDAY = {
    newyear: ["New Year's Day", "a tiny gold party hat", "a sparkly gold and black party hat and a shiny star-shaped confetti collar", "a tall gold and black party hat, a big star-shaped confetti collar and a large round firework-burst medallion on its chest"],
    lunar: ["Lunar New Year", "a small red paper-lantern charm on a gold collar", "a red and gold silk vest with gold cloud patterns and a red paper-lantern charm on a collar", "a red and gold silk jacket with cloud patterns, a lion-dance style headdress with a red and gold mane, and a large round red lantern resting on the ground beside it, attached to its side"],
    valentine: ["Valentine's Day", "a collar with a small red heart charm", "a pink and red heart pattern on its body and a collar with a big puffy red heart charm", "a pink bow on its head, a heart-pattern collar and a big puffy red heart pillow resting on the ground beside it, attached to its side"],
    stpatrick: ["St. Patrick's Day", "a green bow tie with a small shamrock", "a small green top hat with a gold buckle and a shamrock-pattern green bow tie", "a big green leprechaun top hat with a gold buckle, a green waistcoat and a small pot of gold coins resting on the ground beside it, attached to its side"],
    easter: ["Easter", "a small pastel bow with a painted-egg charm", "a pastel bunny-ear headband and a collar of pastel painted-egg charms", "a pastel bunny-ear headband, a pastel bow tie and a big woven basket of painted eggs resting on the ground beside it, attached to its side"],
    eid: ["Ramadan and Eid", "a small gold crescent-moon charm on a collar", "a gold crescent-moon and star medallion on a collar and a rich teal and gold patterned vest", "a teal and gold embroidered vest, a gold crescent-moon medallion and a big ornate lantern resting on the ground beside it, attached to its side"],
    cinco: ["Cinco de Mayo", "a colorful striped scarf", "a small embroidered sombrero and a colorful striped serape draped over its back", "a wide embroidered sombrero, a striped serape over its back and a big garland of colorful paper flowers around its neck"],
    mother: ["Mother's Day", "a small pink flower pendant", "a crown of pink and yellow flowers and a flower-shaped pendant", "a full crown of pink and yellow flowers, a flower garland around its neck and a big bouquet of flowers resting on the ground beside it, attached to its side"],
    father: ["Father's Day", "a small navy bow tie", "a navy bow tie and a small flat cap", "a flat cap, a navy bow tie, a checked vest and a big gold trophy cup resting on the ground beside it, attached to its side"],
    pride: ["Pride Month", "a small rainbow heart pendant", "a rainbow-striped scarf and a rainbow heart pendant", "a rainbow-striped cape draped over its back, a rainbow scarf and a big rainbow heart resting on the ground beside it, attached to its side"],
    juneteenth: ["Juneteenth", "a small red, black and green striped bow", "a red, black and green striped scarf and a gold star pendant", "a red, black and green striped vest, a gold star pendant and a large starburst medallion on its chest"],
    july4: ["Independence Day", "a small star-spangled bandana", "a red, white and blue star-spangled bandana and a small striped top hat", "a tall striped top hat with stars, a red, white and blue bandana and a big star-shaped shield resting on the ground beside it, attached to its side"],
    rosh: ["Rosh Hashanah", "a small red apple charm on a collar", "a collar with a big red apple charm and a small honey-pot charm", "a collar with a red apple charm and a big round honey pot resting on the ground beside it, attached to its side"],
    diwali: ["Diwali", "a small marigold garland", "a garland of orange marigolds and a gold medallion shaped like a diya oil lamp, with colorful rangoli patterns on its back", "a marigold garland, a gold embroidered vest with rangoli patterns and a large diya oil lamp resting on the ground beside it, attached to its side"],
    halloween: ["Halloween", "a tiny purple witch hat", "a small purple witch hat and an orange and black jack-o'-lantern collar charm", "a big purple witch hat, a black cape with an orange lining and a large jack-o'-lantern pumpkin resting on the ground beside it, attached to its side"],
    dia: ["Día de los Muertos", "simple sugar-skull face paint", "colorful sugar-skull face paint, a crown of orange marigolds and a bright papel-picado-pattern scarf", "sugar-skull face paint, a big crown of marigolds, a papel-picado scarf and a large decorated sugar skull resting on the ground beside it, attached to its side"],
    thanksgiving: ["Thanksgiving", "a small autumn-leaf scarf", "a small brown pilgrim-style hat and an autumn scarf with orange, red and yellow leaves", "a brown pilgrim-style hat, an autumn-leaf scarf and a big cornucopia horn full of fruit resting on the ground beside it, attached to its side"],
    hanukkah: ["Hanukkah", "a small blue dreidel charm on a collar", "a blue and white striped scarf and a collar with a chunky blue dreidel charm", "a blue and white knit scarf and hat and a large chunky blue dreidel resting on the ground beside it, attached to its side"],
    christmas: ["Christmas", "a small red santa hat", "a red santa hat with a white band and pompom and a green holly collar with red berries", "a big red santa hat, a green holly collar, a red and white striped scarf and a large wrapped gift box resting on the ground beside it, attached to its side"],
    kwanzaa: ["Kwanzaa", "a small red, black and green kente-pattern bow", "a red, black and green kente-pattern scarf and a small woven kufi cap", "a kente-pattern scarf, a woven kufi cap and a big woven basket of fruit resting on the ground beside it, attached to its side"]
  };

  var BODY = {
    four: "Standing on all four legs, body level, head facing straight forward and level. Legs straight and slightly apart so no leg hides another in the front view; feet flat on the ground.",
    sit: "Sitting upright on its haunches, front legs straight down and slightly apart with the front feet flat on the ground, head facing straight forward. Symmetrical pose.",
    belly: "Lying on its belly with the body resting on the ground, head raised and facing straight forward, front limbs or flippers resting on the ground on both sides. Symmetrical pose.",
    two: "Standing upright on two legs, feet flat on the ground and slightly apart, head facing straight forward. Arms held slightly away from the body and angled down, not touching the body and not raised; hands empty.",
    bird: "Standing on two legs with both feet flat on the ground, body upright or tilted slightly forward, head facing straight forward. Legs short and thick enough to print.",
    many: "Standing on all of its legs, with the legs spread evenly and symmetrically to both sides and every foot touching the ground. Body level, head facing straight forward. Legs thick and short enough to print; no leg crosses over another.",
    snake: "Lying on the ground with the whole body resting flat on the ground, head raised slightly and facing straight forward. Behind the head the body runs back in one wide, gentle S-curve lying flat on the ground, so the curve shows clearly in the top view. No coils stacked on top of each other, no knots, no part of the body crossing over another part.",
    swim: "Shown in a level swimming pose, body horizontal, head facing straight forward, fins and flippers in their natural resting position and thick enough to print.",
    tentacle: "Sitting upright on the ground, head facing straight forward. Tentacles spread evenly around the body and resting flat on the ground in a symmetrical star, tips curling slightly. Tentacles thick and tapered; no tentacle crosses over another.",
    blob: "Sitting on the ground, rounded and symmetrical, facing straight forward.",
    custom: "Neutral, symmetrical resting pose that suits this creature, facing straight forward, with every part that touches the ground resting flat on it."
  };

  var PROPORTIONS = {
    chibi: "Cute, chunky proportions: big head, short thick limbs, rounded shapes.",
    plush: "Plush-toy proportions: soft rounded shapes, a big head, short thick stubby limbs and no sharp details, like a stuffed animal.",
    chubby: "Chubby, round body with thick limbs and a slightly large head.",
    baby: "Baby animal proportions: a large head and eyes, a short body and short thick legs.",
    cartoon: "Stylized cartoon proportions: a slightly larger head and expressive features, otherwise close to the real animal, with thick sturdy limbs.",
    natural: "Natural proportions, like the real animal, but with limbs, horns and other thin parts slightly thicker so they print well.",
    slender: "Tall, slender, elegant proportions, but every leg, neck, horn and tail is still thick enough to print.",
    bulky: "Big, bulky, powerful proportions: a heavy body, thick limbs and large feet or paws.",
    asis: ""
  };

  var WINGS = {
    none: "No wings.",
    folded: "Wings closed and folded flat against the sides of the body, in exactly the same position in every view.",
    flat: "Wings spread straight out to the sides and held flat and horizontal, like a gliding bird. In the front and back views the wings are seen edge-on as thin horizontal shapes; only the top view shows the full wing shape. Same position in every view.",
    upright: "Wings raised upright above the shoulders and opened sideways in one flat vertical plane, facing the viewer in the front view. The front and back views show the full wing shape; in the top view the wings are seen edge-on as thin lines. Same position in every view."
  };

  var SAME = " Same position in every view.";
  var TAIL = {
    none: "No tail.",
    short: "Short stubby tail close to the body, pointing straight back." + SAME,
    feathers: "Short tail feathers pointing straight back along the body's center line." + SAME,
    long: "Long tail extending straight back along the body's center line and resting on or near the ground, with no sideways bend, curl or spiral." + SAME,
    hang: "Thick tail hanging straight down behind the body along its center line, ending near the ground, with no sideways swing." + SAME,
    up: "Long tail rising up behind the body along its center line, curving only forward or backward, never to either side." + SAME,
    bushy: "Big, thick, bushy tail raised behind the body along its center line, curving up and slightly forward, never to either side." + SAME,
    spiral: "Tail curls downward into a flat spiral that lies in the body's center plane, with no sideways twist." + SAME,
    finv: "Tail fin standing upright (vertical) at the end of the body, pointing straight back." + SAME,
    flukes: "Horizontal tail flukes spread flat to both sides at the end of the body, pointing straight back, like a whale or dolphin." + SAME,
    paddle: "Wide, flat paddle-shaped tail lying flat on the ground straight behind the body." + SAME,
    fan: "Tail feathers (or several tails) fanned out upright behind the body in one flat vertical plane, symmetrical, facing the viewer in the front view. In the side and top views the fan is seen edge-on as a thin shape." + SAME
  };

  var BASE = {
    none: "",
    round: "The creature stands on a simple, low, flat round base in one plain color (counted as one of the colors), centered under the creature and identical in every view.",
    oval: "The creature stands on a simple, low, flat oval base in one plain color (counted as one of the colors), centered under the creature, its long side running front to back, and identical in every view."
  };

  var FLAT = " Each body region is one uniform color. No shading, no shadows, no gradients, no highlights, no reflections, no texture, no noise.";
  var STYLE = {
    flat:      function (n) { return "Flat cartoon colors using only " + n + " clearly different solid colors." + FLAT; },
    kawaii:    function (n) { return "Kawaii sticker-style cartoon: very simple rounded shapes and small simple face features, using only " + n + " clearly different solid colors." + FLAT; },
    vinyl:     function (n) { return "Designer vinyl-toy figure look: smooth, simplified, rounded forms with a matte surface, using only " + n + " clearly different solid colors." + FLAT; },
    clay:      function (n) { return "Clay figure look: soft, rounded, hand-sculpted shapes with a matte surface, using only " + n + " clearly different solid colors. Each body region is one even color with no visible lighting, shadows, fingerprints or texture."; },
    cel:       function (n) { return "Anime cel style using only " + n + " clearly different flat colors, with no shadow tones." + FLAT; },
    lowpoly:   function (n) { return "Low-poly look: the creature is built from large flat polygon facets. All facets of one body region share the same flat color, using only " + n + " clearly different colors in total. No lighting differences between facets, no gradients, no texture."; },
    voxel:     function (n) { return "Blocky voxel look: the creature is built from chunky cubes, each cube one flat color, using only " + n + " clearly different colors in total. No lighting differences between cube faces, no shadows, no texture."; },
    stylized:  function (n) { return "Simple stylized colors with at most " + n + " main colors and only very light shading. No cast shadows, no strong gradients, no glossy highlights, no texture noise."; },
    storybook: function (n) { return "Storybook illustration with soft, light shading and simple textures, using at most " + n + " main colors. No cast shadows, no dark shading, no glossy highlights."; },
    realistic: function (n) { return "Realistic painted look with natural markings, using at most " + n + " main colors. Even, flat lighting from the front: no cast shadows, no dark shading, no glossy highlights."; }
  };

  try {
    var saved = JSON.parse(localStorage.getItem(KEY) || "null");
    if (saved) ids.forEach(function (k) {
      var el = $(k);
      if (!el || typeof saved[k] !== "string") return;
      var before = el.value;
      el.value = saved[k];
      if (el.tagName === "SELECT" && el.value === "") el.value = before;
    });
  } catch (e) {}

  function clean(s) { return s.replace(/\s+/g, " ").trim().replace(/[.\s]+$/, ""); }

  function notes() {
    var out = [];
    var body = $("body").value, wings = $("wings").value, tail = $("tail").value, base = $("base").value;
    var style = $("style").value, outlines = $("outlines").value;
    var desc = $("creature").value.toLowerCase();
    if (wings === "flat" || wings === "upright")
      out.push("Spread wings are thin and fragile in print, and are the part most often drawn differently between views. Folded wings are the safer choice.");
    if ((body === "swim" || body === "bird") && base === "none")
      out.push("This body type usually needs a base to stand up in the print.");
    if (body === "snake" && tail !== "none")
      out.push("For snakes the body already ends in the tail, so \"No tail\" avoids an extra part.");
    if (tail === "up" || tail === "bushy" || tail === "fan")
      out.push("A raised or fanned tail is tall and thin and may need supports. A tail on the ground prints more easily.");
    if (style === "storybook" || style === "realistic")
      out.push("Shaded styles make color matching harder: shadows can turn into extra filament colors. Flat styles work best.");
    if (style === "lowpoly" || style === "voxel")
      out.push("Low-poly and voxel sheets have not been tested in the studio yet.");
    if (outlines === "thick" || outlines === "thin")
      out.push("Black outlines will print as black filament and use one of your colors. Very thin lines may be removed by the color stage instead.");
    if (outlines === "none" && /\b(white|snowy|polar|silver)\b/.test(desc))
      out.push("White parts on the edge of the creature can be cut off when the studio finds the figures (the fox's white tail tip was). The prompt asks for tinted whites; thin or thick outlines also help.");
    if ($("layout").value === "grid5")
      out.push("The studio is built around front, side, back and top. A bottom picture has not been tested: check at checkpoint 1 how it is detected and labelled, and leave it out if it gets in the way.");
    if ($("holiday").value !== "none" && $("propSize").value === "large")
      out.push("Large props add colors and cover more of the creature, which can cause color issues in the final file. They are also extra parts for the 3D stage.");
    if ($("holiday").value !== "none") out.push("Studio: when you upload this sheet in Image to 3D, tick \"Has props included\" so the prop colours are kept.");  // PROPS_TOGGLE_V1
    $("notes").innerHTML = out.map(function (t) { return '<p class="pb-hint warn">' + t + "</p>"; }).join("");
  }

  function build() {
    var creature = clean($("creature").value) || "[describe the creature here]";
    var n = $("colors").value;
    var grid = $("layout").value !== "row";
    var base = $("base").value;
    var outl = $("outlines").value;

    var views = [
      "FRONT view (the creature faces the viewer)",
      "LEFT SIDE view (the creature's left side; it faces the left edge of the image)",
      "BACK view (seen from directly behind)",
      "TOP view (looking straight down from above; the creature's front points to the top edge of the image)"
    ];
    var extraV = $("layout").value === "grid5" ? "bottom" : "none";
    if (extraV === "bottom") views.push("BOTTOM view (looking straight up from below at the underside; the creature's front points to the top edge of the image)");
    var nv = views.length;
    var word = nv === 5 ? "five" : "four";
    var layout;
    if (grid && nv === 4) {
      layout = "LAYOUT: One square image divided into a 2x2 grid of four equal panels with clear white space between them.\n" +
        "- Top-left: " + views[0] + ".\n- Top-right: " + views[1] + ".\n- Bottom-left: " + views[2] + ".\n- Bottom-right: " + views[3] + ".";
    } else if (grid) {
      layout = "LAYOUT: One image (about 3:2) with five equal square panels and clear white space between them: three panels in the top row and two panels centered in the bottom row.\n" +
        "- Top row, left to right: " + views[0] + "; " + views[1] + "; " + views[2] + ".\n" +
        "- Bottom row, left to right: " + views[3] + "; " + views[4] + ".";
    } else {
      layout = "LAYOUT: One wide image (about " + nv + ":1) with " + word + " equal square panels side by side and clear white space between them. Left to right:\n" +
        views.map(function (v, i) { return (i + 1) + ". " + v + "."; }).join("\n");
    }
    var camExtra = extraV === "bottom" ? " The bottom camera is directly underneath, looking straight up" + (base === "none" ? "; it shows the underside of the body, the soles of the feet and the underside of the tail." : "; with the base, it shows only the flat underside of the base.") : "";

    var outlines = {
      none: "No outlines: color regions meet directly. Color white or very light parts a clearly tinted cream, pale pink or pale blue rather than pure white or light gray, so they stand out from the white background.",
      thin: "Only thin, even, pure black outlines around the silhouette and between color regions; no sketch lines or hatching. Black counts as one of the " + n + " colors. White or very light parts are fully enclosed by the outline.",
      thick: "Bold, thick, uniform pure black outlines, like a coloring book or sticker, around the whole silhouette and between the main color regions. The outline has the same thickness everywhere and is drawn the same way in every view. Black counts as one of the " + n + " colors. White or very light parts are fully enclosed by the outline."
    }[outl];

    var pose = [BODY[$("body").value], PROPORTIONS[$("proportions").value], WINGS[$("wings").value], TAIL[$("tail").value], BASE[base], "Mouth closed. Nothing held, nothing floating."]
      .filter(Boolean).join(" ");

    var groundWord = base === "none" ? "No floor" : "No floor other than the base";

    var p = [];
    p.push("Create a multiview orthographic reference sheet (character turnaround for 3D modeling) of ONE creature: " + creature + ".");
    var hol = HOLIDAY[$("holiday").value];
    if (hol) {
      p.push("");
      var ps = $("propSize").value;
      var item = hol[ps === "small" ? 1 : ps === "large" ? 3 : 2];
      var sizeRule = {
        small: "Keep the props small and few: they cover only a small part of the creature, and its own colors stay the main colors.",
        medium: "Accessories are chunky, simple and worn snugly.",
        large: "Props are large and bold but still chunky and solid. Any prop beside the creature stands on the same ground line" + (base === "none" ? "" : " on the base") + ", touches and is attached to the creature, and never floats."
      }[ps];
      p.push("HOLIDAY THEME (" + hol[0] + ", " + ps + " props): The creature has " + item + ". " + sizeRule + " Every prop is attached to the creature, drawn exactly the same and in the same place in every view, and uses colors from the same " + n + "-color limit.");
    }
    p.push("");
    p.push(layout);
    p.push("");
    p.push("CAMERA: True orthographic projection in every panel. No perspective, no foreshortening, no 3/4 angles, no tilt. The front, side and back cameras are level with the creature's mid-height. The top camera is directly overhead." + camExtra);
    p.push("");
    p.push("CONSISTENCY: It is the exact same creature in the same pose, with the same proportions and the same size in all " + word + " panels, as if one 3D model were rendered from " + word + " cameras. Front, side and back views stand on the same ground line at the same height. Every limb, fin, horn, color marking and accessory is in the same place on the body in every view, and the number of legs, wings, tails and other parts is the same in every view. The back view is the true back: a feature on the creature's left side appears on the viewer's right in the front view and on the viewer's left in the back view. Do not redraw or re-pose the creature between views.");
    p.push("");
    p.push("POSE: " + pose);
    p.push("");
    p.push("SHAPE (for 3D printing): Solid, sturdy shapes. Every part is attached to the body. No thin wires, whiskers, antennae thinner than a finger, hair strands, chains, loose fabric, tiny spikes, or see-through or glowing parts.");
    p.push("");
    p.push("COLOR: " + STYLE[$("style").value](n) + " " + outlines);
    p.push("");
    p.push("SIZE: In each panel the creature is centered and fills about 80-85% of the panel, never cropped, with a clear margin on every side.");
    p.push("");
    p.push("BACKGROUND: Plain pure white (#FFFFFF) everywhere. " + groundWord + ", no ground shadow, no scenery, no grid lines, no panel borders, no text, no labels, no arrows, no watermark.");
    p.push("");
    p.push("AVOID: perspective, 3/4 views, action poses, a different pose in any view, a mirrored back view, parts that move or change shape between views, extra or missing limbs, wings, tails or fins, cropped body parts, cast shadows, gradients, glossy highlights, more than " + n + " colors, text or labels, background details, more than one creature per panel.");

    $("prompt").value = p.join("\n");
    $("propSize").disabled = $("holiday").value === "none";

    var d = $("diagram");
    d.className = "panels " + (grid ? (nv === 5 ? "g32" : "g2") : (nv === 5 ? "r5" : "r4"));
    d.innerHTML =
      '<div><span><b>FRONT</b>faces you</span></div>' +
      '<div><span><b>LEFT SIDE</b>faces &larr;</span></div>' +
      '<div><span><b>BACK</b>from behind</span></div>' +
      '<div><span><b>TOP</b>front &uarr;</span></div>' +
      (extraV === "bottom" ? '<div><span><b>BOTTOM</b>underside</span></div>' : "") +
"";

    notes();

    try {
      var s = {}; ids.forEach(function (k) { s[k] = $(k).value; });
      localStorage.setItem(KEY, JSON.stringify(s));
    } catch (e) {}
  }

  fillPresets("");
  $("presetSearch").addEventListener("input", function () { fillPresets(this.value); });

  $("example").addEventListener("change", function () {
    var p = PRESETS[this.value];
    if (!p) return;
    $("body").value = p[1];
    $("wings").value = p[2];
    $("tail").value = p[3];
    $("base").value = p[4];
    $("creature").value = p[5];
    build();
    say(p[0] + " loaded. Edit anything you like.");
  });

  ids.forEach(function (k) {
    $(k).addEventListener("input", build);
    $(k).addEventListener("change", build);
  });
  $("form").addEventListener("submit", function (e) { e.preventDefault(); });

  var timer;
  function say(msg) {
    $("status").textContent = msg;
    clearTimeout(timer);
    timer = setTimeout(function () { $("status").textContent = ""; }, 3000);
  }

  $("copy").addEventListener("click", function () {
    var text = $("prompt").value;
    var fallback = function () {
      var t = $("prompt"); t.focus(); t.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (e) {}
      say(ok ? "Copied." : "Text selected. Press Ctrl+C to copy.");
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { say("Copied."); }, fallback);
    } else { fallback(); }
  });

  build();
})();
}

// ---------- .3mf Repair (future project placeholder) ----------
function buildRepair(root){
 if(root.dataset.built)return;root.dataset.built='1';
 const wall=make('div',undefined,'r404-wall');
 const items=[['big','404',2,4],['tile','404: FILAMENT NOT FOUND',8,30],['glitch','ERR_PRINT_NOT_FOUND',62,8],['term','$ repair model.3mf\n> error 404: fix not found',58,62],
  ['tile','ME: FIXES ONE ERROR\n3MF: 404 NEW ERRORS',4,62],['big','404',60,30],['glitch','404 • 404 • 404',30,86],['tile','THIS PAGE IS NOT\nNON-MANIFOLD.\nIT IS JUST MISSING.',70,78],
  ['term','> slicing...\n> page.exe stopped responding (404)',6,84],['tile','SUCH EMPTY\nMUCH 404\nWOW',36,14],['glitch','NOT FOUND',80,44],['tile','THE NOZZLE\nIS FINE.\nTHE PAGE IS 404.',22,44]];
 items.forEach(([cls,text,x,y],i)=>{const n=make('div',undefined,'r404 '+cls);n.style.left=x+'%';n.style.top=y+'%';n.style.transform='rotate('+((i*37)%17-8)+'deg)';
  text.split('\n').forEach((t,j)=>{if(j)n.append(make('br'));n.append(document.createTextNode(t));});wall.append(n);});
 const note=make('div',undefined,'r404-note');note.append(make('h2','.3mf Repair — coming later'),
  make('p','I want a place you can input a .3mf that has a print issue, and it can automatically fix the issues and re-export a working .3mf'));
 root.append(wall,note);
}

// ---------- start (other scripts add their parts at different times: retry for a while, all steps are idempotent) ----------
let tries=0;
function tick(){
 const ok=arrangeHeader();const tabs=buildTabs();
 remember($('hunyuan-create'),'image');remember($('create-panel'),'legacy');
 if(!(ok&&tabs)&&tries++<80)setTimeout(tick,250);
}
tick();
if(header)new MutationObserver(()=>arrangeHeader()).observe(header,{childList:true});
})();
