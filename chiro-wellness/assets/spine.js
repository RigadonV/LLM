/* Chiro Wellness — hero scene (three.js)
 * A stylised human spine that eases from misaligned into alignment on load,
 * then slowly turns while a gold "nerve" pulse travels down the discs.
 * three.js loads from the CDN set in the <script type="importmap"> in index.html.
 *
 * Performance: all 24 vertebrae are one instanced mesh and all discs another,
 * so the whole scene is ~5 draw calls. Rendering pauses when the hero is off
 * screen, and resolution steps down automatically on slow devices.
 */
(function () {
  "use strict";

  var canvas = document.getElementById("spine-canvas");
  if (!canvas) return;
  var root = document.documentElement;

  function fallback(err) {
    root.classList.add("no-webgl");
    if (err) console.warn("3D hero unavailable:", err);
  }

  Promise.all([
    import("three"),
    import("three/addons/environments/RoomEnvironment.js"),
    import("three/addons/utils/BufferGeometryUtils.js")
  ])
    .then(function (m) { init(m[0], m[1].RoomEnvironment, m[2].mergeGeometries); })
    .catch(fallback);

  function init(THREE, RoomEnvironment, mergeGeometries) {
    var renderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
    } catch (e) { return fallback(e); }

    var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var coarse = window.matchMedia("(pointer: coarse)").matches;
    var maxDpr = Math.min(window.devicePixelRatio || 1, coarse ? 1.5 : 2);
    var dpr = maxDpr;
    renderer.setPixelRatio(dpr);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.setClearColor(0x000000, 0);

    var scene = new THREE.Scene();
    var pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();

    var camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
    camera.position.set(0, 0, 15);

    /* Lights: warm key, teal rim, gold fill from below */
    var key = new THREE.DirectionalLight(0xfff1dc, 1.7); key.position.set(5, 6, 7); scene.add(key);
    var rim = new THREE.DirectionalLight(0x3cc4a8, 3.2); rim.position.set(-6, 3, -5); scene.add(rim);
    var fill = new THREE.PointLight(0xf0a500, 18, 20, 2); fill.position.set(2.5, -5, 3); scene.add(fill);
    scene.add(new THREE.HemisphereLight(0xcff5ec, 0x071c19, 0.35));

    /* ------------------------------------------------------------ */
    /* Geometry                                                      */
    /* ------------------------------------------------------------ */
    function roundedDisc(r, h, bevel, segments) {
      var pts = [new THREE.Vector2(0, -h / 2)];
      var n = 8, i, a;
      for (i = 0; i <= n; i++) { a = -Math.PI / 2 + (i / n) * (Math.PI / 2); pts.push(new THREE.Vector2(r - bevel + Math.cos(a) * bevel, -h / 2 + bevel + Math.sin(a) * bevel)); }
      for (i = 0; i <= n; i++) { a = (i / n) * (Math.PI / 2); pts.push(new THREE.Vector2(r - bevel + Math.cos(a) * bevel, h / 2 - bevel + Math.sin(a) * bevel)); }
      pts.push(new THREE.Vector2(0, h / 2));
      return new THREE.LatheGeometry(pts, segments || 48);
    }

    // Place a part geometry into vertebra space: spine axis = +Y, front = +Z.
    var tmp = new THREE.Object3D();
    function placed(geo, pos, rot, scale) {
      tmp.position.set(pos[0], pos[1], pos[2]);
      tmp.rotation.set(rot[0], rot[1], rot[2]);
      tmp.scale.set(scale[0], scale[1], scale[2]);
      tmp.updateMatrix();
      return geo.applyMatrix4(tmp.matrix);
    }

    var vertebraGeo = mergeGeometries([
      placed(roundedDisc(0.62, 0.44, 0.12, 40), [0, 0, 0], [0, 0, 0], [1, 1, 0.82]),                       // body
      placed(new THREE.TorusGeometry(0.3, 0.075, 10, 32), [0, 0.02, -0.74], [Math.PI / 2, 0, 0], [1, 1, 1.6]), // arch
      placed(new THREE.CapsuleGeometry(0.075, 0.62, 4, 10), [0, -0.2, -1.32], [Math.PI / 2 + 0.55, 0, 0], [1, 1, 1]), // spinous process
      placed(new THREE.CapsuleGeometry(0.065, 0.46, 4, 10), [-0.55, 0.04, -0.72], [0, -0.35, Math.PI / 2 + 0.18], [1, 1, 1]), // transverse L
      placed(new THREE.CapsuleGeometry(0.065, 0.46, 4, 10), [0.55, 0.04, -0.72], [0, 0.35, Math.PI / 2 - 0.18], [1, 1, 1])   // transverse R
    ]);
    var discGeo = roundedDisc(0.57, 0.13, 0.055, 36);

    var boneMat = new THREE.MeshPhysicalMaterial({
      color: 0xe9f1ee, roughness: 0.36, metalness: 0.0,
      clearcoat: 0.75, clearcoatRoughness: 0.22, envMapIntensity: 0.8
    });
    var discMat = new THREE.MeshStandardMaterial({
      color: 0xffffff, roughness: 0.28, metalness: 0.15,
      emissive: 0x3a2600, envMapIntensity: 0.9
    });

    /* ------------------------------------------------------------ */
    /* Spine layout: 7 cervical, 12 thoracic, 5 lumbar               */
    /* ------------------------------------------------------------ */
    var N = 24, i;
    var specs = [], totalH = 0;
    for (i = 0; i < N; i++) {
      var t = i / (N - 1);
      var s = 0.5 + 0.62 * Math.pow(t, 0.85);   // larger toward the lumbar end
      specs.push({ t: t, s: s, h: s * 0.62 });
      totalH += s * 0.62;
    }
    var y = totalH / 2;
    specs.forEach(function (sp) {
      sp.y = y - sp.h / 2;
      y -= sp.h;
      sp.z = 0.42 * Math.cos(sp.t * Math.PI * 2) + 0.06; // gentle S-curve
    });
    specs.forEach(function (sp, k) {
      var a = specs[Math.max(0, k - 1)], b = specs[Math.min(N - 1, k + 1)];
      sp.tilt = Math.atan2(a.z - b.z, a.y - b.y);
      // Starting misalignment that each vertebra "adjusts" out of.
      var rnd = function (n) { var x = Math.sin((k + 1) * 12.9898 + n * 78.233) * 43758.5453; return (x - Math.floor(x)) * 2 - 1; };
      sp.off = [rnd(1) * 0.9, rnd(2) * 0.25, rnd(3) * 0.6];
      sp.rot = [rnd(4) * 0.35, rnd(5) * 0.9, rnd(6) * 0.4];
    });

    var discSpecs = [];
    for (i = 0; i < N - 1; i++) {
      var a = specs[i], b = specs[i + 1];
      discSpecs.push({ y: (a.y + b.y) / 2, z: (a.z + b.z) / 2, tilt: (a.tilt + b.tilt) / 2, s: (a.s + b.s) / 2 });
    }

    var spine = new THREE.Group();
    var rig = new THREE.Group();
    rig.add(spine);
    scene.add(rig);

    var vertebrae = new THREE.InstancedMesh(vertebraGeo, boneMat, N);
    var discs = new THREE.InstancedMesh(discGeo, discMat, N - 1);
    vertebrae.frustumCulled = discs.frustumCulled = false;
    vertebrae.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    discs.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    var gold = new THREE.Color(0xf0a500), c = new THREE.Color();
    for (i = 0; i < N - 1; i++) discs.setColorAt(i, gold);
    spine.add(vertebrae, discs);

    /* Orbital rings and floating particles */
    var ringMat = new THREE.MeshBasicMaterial({ color: 0xf0a500, transparent: true, opacity: 0.28, depthWrite: false });
    var ringA = new THREE.Mesh(new THREE.TorusGeometry(3.6, 0.006, 8, 240), ringMat);
    var ringB = new THREE.Mesh(new THREE.TorusGeometry(4.4, 0.004, 8, 240), ringMat.clone());
    ringB.material.color.set(0x3cc4a8); ringB.material.opacity = 0.22;
    ringA.rotation.set(1.25, 0.2, 0); ringB.rotation.set(1.4, -0.35, 0.3);
    rig.add(ringA, ringB);

    function dotTexture() {
      var cv = document.createElement("canvas"); cv.width = cv.height = 64;
      var g = cv.getContext("2d");
      var grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
      grd.addColorStop(0, "rgba(255,255,255,1)"); grd.addColorStop(0.35, "rgba(255,255,255,.5)"); grd.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = grd; g.fillRect(0, 0, 64, 64);
      var tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; return tex;
    }
    var P = coarse ? 260 : 420, positions = new Float32Array(P * 3), speeds = new Float32Array(P);
    for (i = 0; i < P; i++) {
      var r = 1.6 + Math.random() * 4.2, th = Math.random() * Math.PI * 2;
      positions[i * 3] = Math.cos(th) * r;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 11;
      positions[i * 3 + 2] = Math.sin(th) * r - 1;
      speeds[i] = 0.12 + Math.random() * 0.35;
    }
    var pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    var particles = new THREE.Points(pGeo, new THREE.PointsMaterial({
      size: 0.07, map: dotTexture(), color: 0x7fe8d2, transparent: true, opacity: 0.6,
      depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true
    }));
    rig.add(particles);

    /* ------------------------------------------------------------ */
    /* Layout                                                        */
    /* ------------------------------------------------------------ */
    var baseTilt = 0.06;
    function resize() {
      var w = canvas.clientWidth, h = canvas.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      var visH = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.position.z;
      var visW = visH * camera.aspect;
      if (camera.aspect > 1.05) {
        // Desktop / landscape: upright spine on the right.
        baseTilt = 0.06;
        rig.scale.setScalar((visH * 0.8) / totalH);
        rig.position.set(visW * 0.22, 0, 0);
      } else {
        // Portrait / mobile: spine lies across the top of the hero, in the
        // band above the copy (see .hero-inner padding-top in styles.css).
        var bandCenterPx = Math.min(196, h * 0.24);
        baseTilt = Math.PI / 2 + 0.05;
        rig.scale.setScalar((visW * 0.9) / totalH);
        rig.position.set(0, ((h / 2 - bandCenterPx) / h) * visH, 0);
      }
      if (reduceMotion) render(10);
    }

    /* ------------------------------------------------------------ */
    /* Animation                                                     */
    /* ------------------------------------------------------------ */
    var pointer = { x: 0, y: 0, tx: 0, ty: 0 };
    window.addEventListener("pointermove", function (e) {
      pointer.tx = (e.clientX / window.innerWidth) * 2 - 1;
      pointer.ty = (e.clientY / window.innerHeight) * 2 - 1;
    }, { passive: true });

    function easeOutBack(x) { var c1 = 1.5, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); }
    function easeOutCubic(x) { return 1 - Math.pow(1 - x, 3); }
    function clamp01(x) { return x < 0 ? 0 : x > 1 ? 1 : x; }

    var STAGGER = 0.045;
    var ASSEMBLED = 0.25 + N * STAGGER + 1.2;  // seconds until every piece has settled
    var PULSE_EVERY = 4.5;
    var settled = false;

    function placeInstances(time) {
      specs.forEach(function (sp, k) {
        var e = easeOutBack(clamp01((time - 0.25 - k * STAGGER) / 1.1)), inv = 1 - e;
        tmp.position.set(sp.off[0] * inv, sp.y + sp.off[1] * inv, sp.z + sp.off[2] * inv);
        tmp.rotation.set(sp.tilt + sp.rot[0] * inv, sp.rot[1] * inv, sp.rot[2] * inv);
        tmp.scale.setScalar(sp.s);
        tmp.updateMatrix();
        vertebrae.setMatrixAt(k, tmp.matrix);
      });
      discSpecs.forEach(function (d, k) {
        var g = easeOutCubic(clamp01((time - 0.7 - k * STAGGER) / 0.7));
        tmp.position.set(0, d.y, d.z);
        tmp.rotation.set(d.tilt, 0, 0);
        tmp.scale.setScalar(Math.max(0.001, g * d.s));
        tmp.updateMatrix();
        discs.setMatrixAt(k, tmp.matrix);
      });
      vertebrae.instanceMatrix.needsUpdate = true;
      discs.instanceMatrix.needsUpdate = true;
    }

    function render(time) {
      if (!settled) {
        placeInstances(time);
        settled = time > ASSEMBLED;
      }

      // Gold pulse travelling down the discs.
      var pulseT = time > ASSEMBLED ? ((time - ASSEMBLED) % PULSE_EVERY) / 1.8 : -1;
      for (var k = 0; k < N - 1; k++) {
        var dist = pulseT - k / (N - 2);
        var glow = pulseT >= 0 ? Math.exp(-dist * dist * 90) : 0;
        discs.setColorAt(k, c.copy(gold).multiplyScalar(1 + glow * 2.4));
      }
      discs.instanceColor.needsUpdate = true;

      // Slow turn, breathing float and pointer parallax.
      pointer.x += (pointer.tx - pointer.x) * 0.04;
      pointer.y += (pointer.ty - pointer.y) * 0.04;
      spine.rotation.y = (reduceMotion ? 0.55 : 0.55 + time * 0.16) + pointer.x * 0.25;
      rig.rotation.x = pointer.y * 0.08;
      rig.rotation.z = baseTilt;
      spine.position.y = reduceMotion ? 0 : Math.sin(time * 0.6) * 0.08;
      ringA.rotation.z = time * 0.05;
      ringB.rotation.z = -time * 0.035;

      if (!reduceMotion) {
        var pos = pGeo.attributes.position.array;
        for (var j = 0; j < P; j++) {
          pos[j * 3 + 1] += speeds[j] * 0.006;
          if (pos[j * 3 + 1] > 5.5) pos[j * 3 + 1] = -5.5;
        }
        pGeo.attributes.position.needsUpdate = true;
      }
      renderer.render(scene, camera);
    }

    /* ------------------------------------------------------------ */
    /* Loop: pause off screen, lower resolution on slow devices      */
    /* ------------------------------------------------------------ */
    var running = false, visible = true, raf = 0;
    var start = performance.now(), last = 0, slowFrames = 0;
    function loop(now) {
      raf = requestAnimationFrame(loop);
      var dt = last ? now - last : 16;
      last = now;
      if (dt > 40 && dt < 500) slowFrames++; else if (slowFrames > 0) slowFrames--;
      if (slowFrames > 30 && dpr > 0.75) {   // ~0.5s of sub-25fps: drop resolution
        dpr = Math.max(0.75, dpr - 0.5);
        renderer.setPixelRatio(dpr);
        resize();
        slowFrames = 0;
      }
      render((now - start) / 1000);
    }
    function play() { if (!running && visible && !document.hidden) { running = true; last = 0; raf = requestAnimationFrame(loop); } }
    function pause() { running = false; cancelAnimationFrame(raf); }

    window.addEventListener("resize", resize);
    resize();
    root.classList.add("webgl-ready");

    if (reduceMotion) { settled = false; render(10); return; }

    // Only animate while the hero is on screen and the tab is visible.
    // (An edge-adjacent canvas still counts as "intersecting", so use the ratio.)
    new IntersectionObserver(function (entries) {
      visible = entries[0].intersectionRatio >= 0.04;
      if (visible) play(); else pause();
    }, { threshold: [0, 0.04, 0.1, 0.25] }).observe(canvas);
    document.addEventListener("visibilitychange", function () { if (document.hidden) pause(); else play(); });
    play();
  }
})();
