/**
 * Health Data Visualization with Three.js
 * Creates 3D visualizations for health metrics like heart rate, blood pressure, etc.
 */

(function() {
    let visualizations = {};

    // Heart rate visualization
    function createHeartRateVisualization(containerId, data) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error(`Container with ID ${containerId} not found`);
            return null;
        }

        // Create a separate scene for this visualization
        const scene = new THREE.Scene();

        // Create camera for this visualization
        const camera = new THREE.PerspectiveCamera(
            75,
            container.clientWidth / container.clientHeight,
            0.1,
            1000
        );
        camera.position.z = 5;

        // Create renderer for this visualization
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setClearColor(0x000000, 0);
        container.appendChild(renderer.domElement);

        // Create heart geometry
        const heartShape = new THREE.Shape();
        const x = 0, y = 0;
        heartShape.moveTo(x + 0.5, y + 0.5);
        heartShape.bezierCurveTo(x + 0.5, y + 0.5, x + 0.4, y, x, y);
        heartShape.bezierCurveTo(x - 0.6, y, x - 0.6, y + 0.7, x - 0.6, y + 0.7);
        heartShape.bezierCurveTo(x - 0.6, y + 1.1, x - 0.3, y + 1.54, x + 0.5, y + 1.9);
        heartShape.bezierCurveTo(x + 1.2, y + 1.54, x + 1.6, y + 1.1, x + 1.6, y + 0.7);
        heartShape.bezierCurveTo(x + 1.6, y + 0.7, x + 1.6, y, x + 1, y);
        heartShape.bezierCurveTo(x + 0.7, y, x + 0.5, y + 0.5, x + 0.5, y + 0.5);

        // Extrude the heart shape
        const extrudeSettings = {
            depth: 0.8,
            bevelEnabled: true,
            bevelSegments: 2,
            steps: 2,
            bevelSize: 0.1,
            bevelThickness: 0.1
        };

        const geometry = new THREE.ExtrudeGeometry(heartShape, extrudeSettings);

        // Create material based on heart rate value
        let color;
        const heartRate = parseInt(data.heartRate);
        if (heartRate < 60) {
            color = 0x3498db; // Blue for low
        } else if (heartRate < 100) {
            color = 0x2ecc71; // Green for normal
        } else {
            color = 0xe74c3c; // Red for high
        }

        const material = new THREE.MeshPhongMaterial({
            color: color,
            specular: 0xffffff,
            shininess: 100
        });

        const heart = new THREE.Mesh(geometry, material);
        scene.add(heart);

        // Add lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        scene.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
        directionalLight.position.set(1, 1, 2);
        scene.add(directionalLight);

        // Center the heart
        heart.geometry.center();

        // Animation object
        const animation = {
            update: function(elapsedTime) {
                // Pulse effect based on heart rate
                const scale = 1 + Math.sin(elapsedTime * heartRate / 30) * 0.1;
                heart.scale.set(scale, scale, scale);

                // Rotate slowly
                heart.rotation.y = elapsedTime * 0.5;
            }
        };

        // Animation loop
        function animate() {
            if (!renderer.domElement.parentNode) return; // Stop if removed from DOM

            requestAnimationFrame(animate);

            const elapsedTime = clock.getElapsedTime();
            animation.update(elapsedTime);

            renderer.render(scene, camera);
        }

        // Create clock for this visualization
        const clock = new THREE.Clock();

        // Handle resize
        function handleResize() {
            if (!container.parentNode) return; // Stop if container is removed

            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        }

        window.addEventListener('resize', handleResize);

        // Start animation
        animate();

        // Store visualization object for later access
        const visualizationId = containerId + '_heartRate';
        visualizations[visualizationId] = {
            scene: scene,
            camera: camera,
            renderer: renderer,
            mesh: heart,
            animation: animation,
            handleResize: handleResize,
            dispose: function() {
                window.removeEventListener('resize', handleResize);

                if (container.contains(renderer.domElement)) {
                    container.removeChild(renderer.domElement);
                }

                geometry.dispose();
                material.dispose();
                renderer.dispose();
            }
        };

        return visualizationId;
    }

    // Blood pressure visualization
    function createBloodPressureVisualization(containerId, data) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error(`Container with ID ${containerId} not found`);
            return null;
        }

        // Create a separate scene for this visualization
        const scene = new THREE.Scene();

        // Create camera for this visualization
        const camera = new THREE.PerspectiveCamera(
            75,
            container.clientWidth / container.clientHeight,
            0.1,
            1000
        );
        camera.position.z = 5;

        // Create renderer for this visualization
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setClearColor(0x000000, 0);
        container.appendChild(renderer.domElement);

        // Create cylindrical tube to represent blood vessel
        const geometry = new THREE.CylinderGeometry(1, 1, 5, 32);

        // Create material with color based on blood pressure
        const systolic = parseInt(data.systolic);
        const diastolic = parseInt(data.diastolic);

        let color;
        if (systolic < 120 && diastolic < 80) {
            color = 0x2ecc71; // Green for normal
        } else if (systolic < 140 && diastolic < 90) {
            color = 0xf39c12; // Orange for elevated
        } else {
            color = 0xe74c3c; // Red for high
        }

        const material = new THREE.MeshPhongMaterial({
            color: color,
            specular: 0xffffff,
            shininess: 100,
            transparent: true,
            opacity: 0.8
        });

        const vessel = new THREE.Mesh(geometry, material);
        vessel.rotation.z = Math.PI / 2; // Rotate to horizontal
        scene.add(vessel);

        // Add blood particles flowing through the vessel
        const particleGeometry = new THREE.BufferGeometry();
        const particleCount = 100;
        const positions = new Float32Array(particleCount * 3);

        for (let i = 0; i < particleCount; i++) {
            positions[i * 3] = Math.random() * 4 - 2; // x position along the vessel
            positions[i * 3 + 1] = Math.random() * 0.5 - 0.25; // y position
            positions[i * 3 + 2] = Math.random() * 0.5 - 0.25; // z position
        }

        particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

        const particleMaterial = new THREE.PointsMaterial({
            color: 0xff0000,
            size: 0.1,
            transparent: true,
            opacity: 0.7
        });

        const particles = new THREE.Points(particleGeometry, particleMaterial);
        scene.add(particles);

        // Add lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        scene.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
        directionalLight.position.set(1, 1, 2);
        scene.add(directionalLight);

        // Animation object
        const animation = {
            update: function(elapsedTime) {
                // Move particles along the vessel
                const positions = particles.geometry.attributes.position.array;
                for (let i = 0; i < particleCount; i++) {
                    const i3 = i * 3;
                    positions[i3] += 0.05; // Move along x-axis

                    // Reset particle position when it reaches the end
                    if (positions[i3] > 2) {
                        positions[i3] = -2;
                    }
                }
                particles.geometry.attributes.position.needsUpdate = true;

                // Pulse effect based on blood pressure
                const scale = 1 + Math.sin(elapsedTime * 2) * 0.05 * (systolic / 120);
                vessel.scale.y = scale;
                vessel.scale.z = scale;
            }
        };

        // Animation loop
        function animate() {
            if (!renderer.domElement.parentNode) return; // Stop if removed from DOM

            requestAnimationFrame(animate);

            const elapsedTime = clock.getElapsedTime();
            animation.update(elapsedTime);

            renderer.render(scene, camera);
        }

        // Create clock for this visualization
        const clock = new THREE.Clock();

        // Handle resize
        function handleResize() {
            if (!container.parentNode) return; // Stop if container is removed

            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        }

        window.addEventListener('resize', handleResize);

        // Start animation
        animate();

        // Store visualization object for later access
        const visualizationId = containerId + '_bloodPressure';
        visualizations[visualizationId] = {
            scene: scene,
            camera: camera,
            renderer: renderer,
            mesh: vessel,
            particles: particles,
            animation: animation,
            handleResize: handleResize,
            dispose: function() {
                window.removeEventListener('resize', handleResize);

                if (container.contains(renderer.domElement)) {
                    container.removeChild(renderer.domElement);
                }

                geometry.dispose();
                material.dispose();
                particleGeometry.dispose();
                particleMaterial.dispose();
                renderer.dispose();
            }
        };

        return visualizationId;
    }

    // Public API
    window.HealthVisualization = {
        createHeartRateVisualization: createHeartRateVisualization,
        createBloodPressureVisualization: createBloodPressureVisualization,

        // Get a visualization by ID
        getVisualization: function(id) {
            return visualizations[id];
        },

        // Dispose a visualization
        disposeVisualization: function(id) {
            if (visualizations[id]) {
                visualizations[id].dispose();
                delete visualizations[id];
            }
        },

        // Dispose all visualizations
        disposeAll: function() {
            for (const id in visualizations) {
                visualizations[id].dispose();
            }
            visualizations = {};
        }
    };
})();
