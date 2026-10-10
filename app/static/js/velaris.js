/*!
 * Velaris — WebGL animated simplex-noise gradient background
 * Ported from React/TypeScript to vanilla JS for RepurposeKit Lite.
 *
 * Usage:
 *   const v = new Velaris(containerElement, { ...options });
 *   v.start();
 *   // later: v.destroy();
 */

const VELARIS_VERTEX_SHADER = `
attribute vec2 position;
varying vec2 vUv;
void main() {
  vUv = position * 0.5 + 0.5;
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const VELARIS_FRAGMENT_SHADER = `
precision highp float;
varying vec2 vUv;

uniform vec2  u_resolution;
uniform float u_time;
uniform float u_grain;
uniform vec3  u_colors[4];
uniform vec3  u_bg;

vec3 permute(vec3 x) { return mod(((x*34.0)+1.0)*x, 289.0); }

float snoise(vec2 v){
  const vec4 C = vec4(0.211324865405187, 0.366025403784439,
           -0.577350269189626, 0.024390243902439);
  vec2 i  = floor(v + dot(v, C.yy));
  vec2 x0 = v - i + dot(i, C.xx);
  vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
  vec4 x12 = x0.xyxy + C.xxzz;
  x12.xy -= i1;
  i = mod(i, 289.0);
  vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0))
         + i.x + vec3(0.0, i1.x, 1.0));
  vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy),
    dot(x12.zw,x12.zw)), 0.0);
  m = m*m;
  m = m*m;
  vec3 x = 2.0 * fract(p * C.www) - 1.0;
  vec3 h = abs(x) - 0.5;
  vec3 ox = floor(x + 0.5);
  vec3 a0 = x - ox;
  m *= 1.79284291400159 - 0.85373472095314 * (a0*a0 + h*h);
  vec3 g;
  g.x  = a0.x  * x0.x  + h.x  * x0.y;
  g.yz = a0.yz * x12.xz + h.yz * x12.yw;
  return 130.0 * dot(m, g);
}

void main() {
  vec2 uv = vUv;
  float ratio = u_resolution.x / u_resolution.y;
  vec2 p = uv - 0.5;
  p.x *= ratio;

  float t = u_time * 0.1;

  float n1 = snoise(p * 0.4  + vec2( t * 0.2,  -t * 0.3));
  float n2 = snoise(p * 0.55 + vec2(-t * 0.15,  t * 0.25) + n1 * 0.25);
  float n3 = snoise(p * 0.75 + vec2( t * 0.1,  -t * 0.2)  + n2 * 0.2);

  vec3 col = u_bg;

  float dist     = length(p) * 1.5;
  float vignette = 1.0 - smoothstep(0.3, 1.2, dist);

  col = mix(col, u_colors[0], smoothstep(-0.2, 0.5, n1)      * 0.85);
  col = mix(col, u_colors[1], smoothstep(-0.1, 0.6, n2)      * 0.7);
  col = mix(col, u_colors[2], smoothstep(-0.3, 0.4, n3)      * 0.6);
  col = mix(col, u_colors[3], smoothstep( 0.0, 0.7, n1 * n2) * 0.5);

  float glow = smoothstep(0.8, 0.0, dist) * 0.3;
  col += u_colors[1] * glow;

  col = mix(col * 0.2, col, vignette);

  float grain = fract(sin(dot(uv, vec2(12.9898, 78.233))) * 43758.5453 + u_time);
  col += (grain - 0.5) * u_grain * 0.1;

  gl_FragColor = vec4(col, 1.0);
}
`;

/**
 * @param {string} hex  e.g. "#0f62fe"
 * @returns {[number, number, number]}  each value 0..1
 */
function hexToRgb(hex) {
  const h = hex.replace('#', '');
  return [
    parseInt(h.slice(0, 2), 16) / 255,
    parseInt(h.slice(2, 4), 16) / 255,
    parseInt(h.slice(4, 6), 16) / 255,
  ];
}

function compileShader(gl, type, src) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src);
  gl.compileShader(s);
  return s;
}

class Velaris {
  /**
   * @param {HTMLElement} container  Element to render into. Must have a defined size.
   * @param {object}      opts
   * @param {string}      opts.bg       Background hex colour   (default: "#0f1117")
   * @param {string[]}    opts.colors   Array of 4 hex colours  (default: IBM blue palette)
   * @param {number}      opts.speed    Animation speed          (default: 2.0)
   * @param {number}      opts.grain    Film-grain intensity     (default: 0.3)
   */
  constructor(container, opts = {}) {
    this._container = container;
    this._opts = Object.assign({
      bg:     '#0f1117',
      colors: ['#4589ff', '#0f62fe', '#0043ce', '#001d6c'],
      speed:  2.0,
      grain:  0.3,
    }, opts);

    this._raf   = null;
    this._ro    = null;
    this._gl    = null;
    this._locs  = null;
    this._canvas = null;
  }

  start() {
    /* ── create canvas ──────────────────────────────────────────────────── */
    const canvas = document.createElement('canvas');
    canvas.style.cssText =
      'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;';
    this._container.appendChild(canvas);
    this._canvas = canvas;

    const gl = canvas.getContext('webgl');
    if (!gl) { console.warn('Velaris: WebGL not supported'); return; }
    this._gl = gl;

    /* ── shader program ─────────────────────────────────────────────────── */
    const program = gl.createProgram();
    gl.attachShader(program, compileShader(gl, gl.VERTEX_SHADER,   VELARIS_VERTEX_SHADER));
    gl.attachShader(program, compileShader(gl, gl.FRAGMENT_SHADER, VELARIS_FRAGMENT_SHADER));
    gl.linkProgram(program);
    gl.useProgram(program);

    /* ── full-screen quad ───────────────────────────────────────────────── */
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER,
      new Float32Array([-1,-1, 1,-1, -1,1, 1,1]), gl.STATIC_DRAW);

    const posLoc = gl.getAttribLocation(program, 'position');
    gl.enableVertexAttribArray(posLoc);
    gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

    /* ── uniform locations ──────────────────────────────────────────────── */
    this._locs = {
      res:    gl.getUniformLocation(program, 'u_resolution'),
      time:   gl.getUniformLocation(program, 'u_time'),
      grain:  gl.getUniformLocation(program, 'u_grain'),
      colors: gl.getUniformLocation(program, 'u_colors'),
      bg:     gl.getUniformLocation(program, 'u_bg'),
    };

    /* ── resize observer ────────────────────────────────────────────────── */
    this._ro = new ResizeObserver(() => this._resize());
    this._ro.observe(this._container);
    this._resize();

    /* ── render loop ────────────────────────────────────────────────────── */
    const loop = (t) => {
      this._render(t);
      this._raf = requestAnimationFrame(loop);
    };
    this._raf = requestAnimationFrame(loop);
  }

  _resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this._canvas.width  = this._container.clientWidth  * dpr;
    this._canvas.height = this._container.clientHeight * dpr;
    this._gl.viewport(0, 0, this._canvas.width, this._canvas.height);
  }

  _render(t) {
    const { gl, _locs: locs, _opts: o } = this;
    if (!gl) return;
    gl.uniform2f(locs.res, this._canvas.width, this._canvas.height);
    gl.uniform1f(locs.time,  t * 0.001 * o.speed);
    gl.uniform1f(locs.grain, o.grain);
    gl.uniform3f(locs.bg, ...hexToRgb(o.bg));
    gl.uniform3fv(locs.colors,
      new Float32Array(o.colors.slice(0, 4).flatMap(hexToRgb)));
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  /** Clean up WebGL context, observers and animation frame. */
  destroy() {
    if (this._raf)  cancelAnimationFrame(this._raf);
    if (this._ro)   this._ro.disconnect();
    if (this._canvas && this._canvas.parentNode)
      this._canvas.parentNode.removeChild(this._canvas);
    this._gl = null;
  }
}
