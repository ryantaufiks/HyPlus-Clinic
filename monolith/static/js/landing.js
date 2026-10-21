/*
 * Home page motion: the 3D particle orb, parallax, scroll reveal and the
 * spotlight on service cards. Pure decoration with no dependencies; it all
 * stops for people who prefer reduced motion and while the tab is hidden.
 */
(function () {
    "use strict";

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    /* ---- Scroll reveal ---------------------------------------------------- */
    const revealed = document.querySelectorAll("[data-reveal]");
    if (!reduceMotion && "IntersectionObserver" in window) {
        document.documentElement.classList.add("js-motion");
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                }
            });
        }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
        revealed.forEach((el) => observer.observe(el));
    } else {
        revealed.forEach((el) => el.classList.add("is-visible"));
    }

    /* ---- Spotlight on cards ----------------------------------------------- */
    document.querySelectorAll(".spotlight").forEach((card) => {
        card.addEventListener("pointermove", (event) => {
            const rect = card.getBoundingClientRect();
            card.style.setProperty("--mx", `${event.clientX - rect.left}px`);
            card.style.setProperty("--my", `${event.clientY - rect.top}px`);
        });
    });

    /* ---- Parallax background ---------------------------------------------- */
    const layers = document.querySelectorAll("[data-depth]");
    if (!reduceMotion && layers.length) {
        let ticking = false;
        window.addEventListener("scroll", () => {
            if (ticking) return;
            ticking = true;
            requestAnimationFrame(() => {
                const y = window.scrollY;
                layers.forEach((layer) => {
                    layer.style.transform = `translate3d(0, ${y * Number(layer.dataset.depth)}px, 0)`;
                });
                ticking = false;
            });
        }, { passive: true });
    }

    /* ---- 3D particle orb -------------------------------------------------- */
    const canvas = document.getElementById("orb");
    if (!canvas || !canvas.getContext) return;
    const ctx = canvas.getContext("2d");

    // Points evenly spread over a sphere (Fibonacci lattice), plus one tilted ring.
    const COUNT = window.innerWidth < 768 ? 420 : 760;
    const points = [];
    const golden = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < COUNT; i++) {
        const y = 1 - (i / (COUNT - 1)) * 2;
        const r = Math.sqrt(1 - y * y);
        points.push({ x: Math.cos(golden * i) * r, y, z: Math.sin(golden * i) * r, ring: false });
    }
    for (let i = 0; i < 140; i++) {
        const a = (i / 140) * Math.PI * 2;
        points.push({ x: Math.cos(a) * 1.35, y: 0, z: Math.sin(a) * 1.35, ring: true });
    }

    let width = 0, height = 0, dpr = 1;
    function resize() {
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        const rect = canvas.getBoundingClientRect();
        width = rect.width;
        height = rect.height;
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    // The pointer tilts the orb a little; it eases towards the target.
    const tilt = { x: 0, y: 0, tx: 0, ty: 0 };
    window.addEventListener("pointermove", (event) => {
        tilt.tx = (event.clientY / window.innerHeight - 0.5) * 0.5;
        tilt.ty = (event.clientX / window.innerWidth - 0.5) * 0.7;
    }, { passive: true });

    function draw(time) {
        ctx.clearRect(0, 0, width, height);
        tilt.x += (tilt.tx - tilt.x) * 0.05;
        tilt.y += (tilt.ty - tilt.y) * 0.05;
        const spin = time * 0.00012 + tilt.y;
        const cosY = Math.cos(spin), sinY = Math.sin(spin);
        const cosX = Math.cos(0.35 + tilt.x), sinX = Math.sin(0.35 + tilt.x);
        const radius = Math.min(width, height) * 0.34;
        const cx = width / 2, cy = height / 2;
        const beat = 1 + 0.025 * Math.max(0, Math.sin(time * 0.0042)) ** 12; // a gentle heartbeat

        for (const p of points) {
            // Rotate around Y, then X; the ring has its own slower tilt.
            let x = p.x * cosY - p.z * sinY;
            let z = p.x * sinY + p.z * cosY;
            let y = p.y;
            if (p.ring) {
                const ry = y * Math.cos(1.1) - z * Math.sin(1.1);
                z = y * Math.sin(1.1) + z * Math.cos(1.1);
                y = ry;
            }
            const y2 = y * cosX - z * sinX;
            const z2 = y * sinX + z * cosX;
            const depth = (z2 + 1.4) / 2.8; // 0 (back) .. 1 (front)
            const scale = (1.6 / (2.6 - z2)) * radius * (p.ring ? 1 : beat);
            const size = (p.ring ? 1.1 : 1.4) * (0.5 + depth) * Math.min(dpr, 1.5);
            ctx.globalAlpha = p.ring ? 0.18 + depth * 0.45 : 0.1 + depth * 0.7;
            ctx.fillStyle = p.ring ? "#2a78d6" : depth > 0.62 ? "#0b7a83" : "#3fb9b3";
            ctx.beginPath();
            ctx.arc(cx + x * scale, cy + y2 * scale, size, 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.globalAlpha = 1;
    }

    let frame = null;
    function loop(time) {
        draw(time);
        frame = requestAnimationFrame(loop);
    }
    function start() {
        if (!frame && !reduceMotion) frame = requestAnimationFrame(loop);
    }
    function stop() {
        if (frame) cancelAnimationFrame(frame);
        frame = null;
    }

    resize();
    window.addEventListener("resize", () => { resize(); if (reduceMotion) draw(0); });
    if (reduceMotion) {
        draw(0);
    } else {
        // Animate only while the orb is on screen and the tab is visible.
        const visible = { onScreen: true };
        new IntersectionObserver(([entry]) => {
            visible.onScreen = entry.isIntersecting;
            visible.onScreen && !document.hidden ? start() : stop();
        }).observe(canvas);
        document.addEventListener("visibilitychange", () => (document.hidden || !visible.onScreen ? stop() : start()));
        start();
    }
})();
