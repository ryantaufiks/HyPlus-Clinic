/**
 * Animated Background with Floating Particles
 * Creates an animated particle system for the background
 */

(function() {
    // Variables for particle system
    let particleSystem;
    let particleCount = 100;
    let particles = [];

    // Initialize animated background
    function init() {
        const scene = window.ThreeJSUtils.getScene();
        if (!scene) {
            console.error('Three.js scene not initialized');
            return;
        }

        // Create particle geometry
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        const sizes = new Float32Array(particleCount);
        const velocities = [];

        // Initialize particle properties
        for (let i = 0; i < particleCount; i++) {
            // Position
            positions[i * 3] = (Math.random() - 0.5) * 20;
            positions[i * 3 + 1] = (Math.random() - 0.5) * 20;
            positions[i * 3 + 2] = (Math.random() - 0.5) * 20;

            // Color (cyan to blue gradient)
            const color = new THREE.Color();
            color.setHSL(0.5 + Math.random() * 0.1, 0.8, 0.5 + Math.random() * 0.2);
            colors[i * 3] = color.r;
            colors[i * 3 + 1] = color.g;
            colors[i * 3 + 2] = color.b;

            // Size
            sizes[i] = Math.random() * 0.5 + 0.1;

            // Velocity
            velocities.push({
                x: (Math.random() - 0.5) * 0.01,
                y: (Math.random() - 0.5) * 0.01,
                z: (Math.random() - 0.5) * 0.01
            });
        }

        // Set geometry attributes
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

        // Create particle material
        const material = new THREE.PointsMaterial({
            size: 0.2,
            vertexColors: true,
            transparent: true,
            opacity: 0.6,
            blending: THREE.AdditiveBlending
        });

        // Create particle system
        particleSystem = new THREE.Points(geometry, material);
        scene.add(particleSystem);

        // Create animation object
        const animation = {
            update: function(elapsedTime) {
                if (!particleSystem) return;

                const positions = particleSystem.geometry.attributes.position.array;

                for (let i = 0; i < particleCount; i++) {
                    const i3 = i * 3;

                    // Update position based on velocity
                    positions[i3] += velocities[i].x;
                    positions[i3 + 1] += velocities[i].y;
                    positions[i3 + 2] += velocities[i].z;

                    // Add some wave motion
                    positions[i3 + 1] += Math.sin(elapsedTime * 0.5 + i) * 0.002;

                    // Wrap particles around when they go out of bounds
                    if (Math.abs(positions[i3]) > 10) velocities[i].x *= -1;
                    if (Math.abs(positions[i3 + 1]) > 10) velocities[i].y *= -1;
                    if (Math.abs(positions[i3 + 2]) > 10) velocities[i].z *= -1;
                }

                particleSystem.geometry.attributes.position.needsUpdate = true;

                // Rotate the entire particle system slowly
                particleSystem.rotation.y = elapsedTime * 0.02;
                particleSystem.rotation.x = elapsedTime * 0.01;
            }
        };

        // Add animation to the Three.js animation loop
        window.ThreeJSUtils.addAnimation(animation);

        // Store reference to animation and velocities for cleanup
        particleSystem.userData.animation = animation;
        particleSystem.userData.velocities = velocities;
    }

    // Clean up function
    function dispose() {
        if (!particleSystem) return;

        const scene = window.ThreeJSUtils.getScene();
        if (scene) {
            // Remove animation from animation loop
            if (particleSystem.userData.animation) {
                window.ThreeJSUtils.removeAnimation(particleSystem.userData.animation);
            }

            // Remove particle system from scene
            scene.remove(particleSystem);

            // Dispose of geometry and material
            if (particleSystem.geometry) particleSystem.geometry.dispose();
            if (particleSystem.material) particleSystem.material.dispose();
        }

        particleSystem = null;
    }

    // Initialize when Three.js is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        // If Three.js is already initialized, initialize now
        if (window.ThreeJSUtils && window.ThreeJSUtils.getScene()) {
            init();
        } else {
            // Otherwise wait for Three.js to initialize
            document.addEventListener('DOMContentLoaded', init);
        }
    }

    // Store dispose function for global access
    window.AnimatedBackground = {
        init: init,
        dispose: dispose
    };
})();
