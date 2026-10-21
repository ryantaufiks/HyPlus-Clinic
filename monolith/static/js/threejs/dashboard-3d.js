/**
 * Interactive 3D Health Metrics Dashboard
 * Creates an interactive 3D visualization of health metrics for the dashboard
 */

(function() {
    let dashboardVisualization = null;
    let raycaster, mouse;
    let selectedMetric = null;

    // Initialize 3D Dashboard
    function initDashboard(containerId, healthData) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error(`Container with ID ${containerId} not found`);
            return null;
        }

        // Clean up existing visualization if any
        if (dashboardVisualization) {
            disposeDashboard();
        }

        // Create scene
        const scene = new THREE.Scene();

        // Create camera
        const camera = new THREE.PerspectiveCamera(
            75,
            container.clientWidth / container.clientHeight,
            0.1,
            1000
        );
        camera.position.z = 10;

        // Create renderer
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setClearColor(0x000000, 0);
        container.appendChild(renderer.domElement);

        // Add lights
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        scene.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
        directionalLight.position.set(1, 1, 2);
        scene.add(directionalLight);

        // Initialize raycaster for interaction
        raycaster = new THREE.Raycaster();
        mouse = new THREE.Vector2();

        // Create 3D visualization components
        const metrics = create3DMetrics(healthData);
        metrics.forEach(metric => scene.add(metric));

        // Handle window resize
        function handleResize() {
            if (!container.parentNode) return;

            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        }

        window.addEventListener('resize', handleResize);

        // Handle mouse interaction
        function handleMouseMove(event) {
            // Calculate mouse position in normalized device coordinates
            // (-1 to +1) for both components
            const rect = container.getBoundingClientRect();
            mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
            mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

            // Update the picking ray with the camera and mouse position
            raycaster.setFromCamera(mouse, camera);

            // Calculate objects intersecting the picking ray
            const intersects = raycaster.intersectObjects(metrics);

            // Reset all metrics to normal state
            metrics.forEach(metric => {
                if (metric.userData.isInteractive) {
                    metric.material.emissive = new THREE.Color(0x000000);
                    metric.scale.set(1, 1, 1);
                }
            });

            // Highlight intersected metrics
            if (intersects.length > 0) {
                const selectedObject = intersects[0].object;
                if (selectedObject.userData.isInteractive) {
                    selectedObject.material.emissive = new THREE.Color(selectedObject.userData.highlightColor);
                    selectedObject.scale.set(1.1, 1.1, 1.1);
                    container.style.cursor = 'pointer';
                } else {
                    container.style.cursor = 'default';
                }
            } else {
                container.style.cursor = 'default';
            }
        }

        function handleClick(event) {
            // Calculate mouse position in normalized device coordinates
            const rect = container.getBoundingClientRect();
            mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
            mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

            // Update the picking ray with the camera and mouse position
            raycaster.setFromCamera(mouse, camera);

            // Calculate objects intersecting the picking ray
            const intersects = raycaster.intersectObjects(metrics);

            if (intersects.length > 0) {
                const selectedObject = intersects[0].object;
                if (selectedObject.userData.isInteractive) {
                    // Trigger custom event with metric data
                    const metricEvent = new CustomEvent('metricSelected', {
                        detail: {
                            name: selectedObject.userData.metricName,
                            value: selectedObject.userData.metricValue,
                            unit: selectedObject.userData.metricUnit
                        }
                    });
                    container.dispatchEvent(metricEvent);
                }
            }
        }

        container.addEventListener('mousemove', handleMouseMove);
        container.addEventListener('click', handleClick);

        // Create animation loop
        const clock = new THREE.Clock();

        function animate() {
            if (!renderer.domElement.parentNode) return;

            requestAnimationFrame(animate);

            const elapsedTime = clock.getElapsedTime();

            // Rotate all metrics slowly
            metrics.forEach(metric => {
                if (metric.userData.autoRotate) {
                    metric.rotation.y = elapsedTime * 0.2;
                    metric.rotation.x = Math.sin(elapsedTime * 0.3) * 0.1;
                }
            });

            renderer.render(scene, camera);
        }

        // Start animation
        animate();

        // Store visualization components for later access
        dashboardVisualization = {
            scene: scene,
            camera: camera,
            renderer: renderer,
            metrics: metrics,
            handleResize: handleResize,
            handleMouseMove: handleMouseMove,
            handleClick: handleClick,
            container: container,
            dispose: function() {
                window.removeEventListener('resize', handleResize);
                container.removeEventListener('mousemove', handleMouseMove);
                container.removeEventListener('click', handleClick);

                if (container.contains(renderer.domElement)) {
                    container.removeChild(renderer.domElement);
                }

                // Dispose all geometries and materials
                metrics.forEach(metric => {
                    if (metric.geometry) metric.geometry.dispose();
                    if (metric.material) metric.material.dispose();
                });

                renderer.dispose();
                dashboardVisualization = null;
            }
        };

        return dashboardVisualization;
    }

    // Create 3D metrics based on health data
    function create3DMetrics(healthData) {
        const metrics = [];
        const positions = [
            { x: -4, y: 2, z: 0 },   // Heart Rate
            { x: 0, y: 2, z: 0 },    // Blood Pressure
            { x: 4, y: 2, z: 0 },    // Weight
            { x: -2, y: -2, z: 0 },  // Temperature
            { x: 2, y: -2, z: 0 }    // Oxygen Saturation
        ];

        // Heart Rate - Pulsating Sphere
        if (healthData.heartRate) {
            const heartRateGeometry = new THREE.SphereGeometry(1, 32, 32);
            const heartRateValue = parseInt(healthData.heartRate);
            let heartRateColor;

            if (heartRateValue < 60) {
                heartRateColor = 0x3498db; // Blue for low
            } else if (heartRateValue < 100) {
                heartRateColor = 0x2ecc71; // Green for normal
            } else {
                heartRateColor = 0xe74c3c; // Red for high
            }

            const heartRateMaterial = new THREE.MeshPhongMaterial({
                color: heartRateColor,
                emissive: 0x000000,
                shininess: 100
            });

            const heartRate = new THREE.Mesh(heartRateGeometry, heartRateMaterial);
            heartRate.position.set(positions[0].x, positions[0].y, positions[0].z);
            heartRate.userData = {
                isInteractive: true,
                metricName: 'Heart Rate',
                metricValue: heartRateValue,
                metricUnit: 'bpm',
                highlightColor: 0x555555,
                autoRotate: true
            };

            metrics.push(heartRate);
        }

        // Blood Pressure - Cylinder with particles
        if (healthData.systolic && healthData.diastolic) {
            const bpGeometry = new THREE.CylinderGeometry(0.8, 0.8, 2, 32);
            const systolicValue = parseInt(healthData.systolic);
            const diastolicValue = parseInt(healthData.diastolic);
            let bpColor;

            if (systolicValue < 120 && diastolicValue < 80) {
                bpColor = 0x2ecc71; // Green for normal
            } else if (systolicValue < 140 && diastolicValue < 90) {
                bpColor = 0xf39c12; // Orange for elevated
            } else {
                bpColor = 0xe74c3c; // Red for high
            }

            const bpMaterial = new THREE.MeshPhongMaterial({
                color: bpColor,
                emissive: 0x000000,
                shininess: 100
            });

            const bloodPressure = new THREE.Mesh(bpGeometry, bpMaterial);
            bloodPressure.position.set(positions[1].x, positions[1].y, positions[1].z);
            bloodPressure.rotation.z = Math.PI / 2; // Rotate to horizontal
            bloodPressure.userData = {
                isInteractive: true,
                metricName: 'Blood Pressure',
                metricValue: `${systolicValue}/${diastolicValue}`,
                metricUnit: 'mmHg',
                highlightColor: 0x555555,
                autoRotate: true
            };

            metrics.push(bloodPressure);
        }

        // Weight - Box
        if (healthData.weight) {
            const weightValue = parseFloat(healthData.weight);
            const normalizedWeight = Math.min(Math.max(weightValue / 100, 0.5), 2); // Normalize to 0.5-2 range

            const weightGeometry = new THREE.BoxGeometry(normalizedWeight, normalizedWeight, normalizedWeight);
            const weightMaterial = new THREE.MeshPhongMaterial({
                color: 0x9b59b6,
                emissive: 0x000000,
                shininess: 100
            });

            const weight = new THREE.Mesh(weightGeometry, weightMaterial);
            weight.position.set(positions[2].x, positions[2].y, positions[2].z);
            weight.userData = {
                isInteractive: true,
                metricName: 'Weight',
                metricValue: weightValue,
                metricUnit: 'kg',
                highlightColor: 0x555555,
                autoRotate: true
            };

            metrics.push(weight);
        }

        // Temperature - Tetrahedron
        if (healthData.temperature) {
            const tempValue = parseFloat(healthData.temperature);
            let tempColor;

            if (tempValue < 36.1) {
                tempColor = 0x3498db; // Blue for low
            } else if (tempValue < 37.2) {
                tempColor = 0x2ecc71; // Green for normal
            } else {
                tempColor = 0xe74c3c; // Red for high
            }

            const tempGeometry = new THREE.TetrahedronGeometry(1.2, 0);
            const tempMaterial = new THREE.MeshPhongMaterial({
                color: tempColor,
                emissive: 0x000000,
                shininess: 100
            });

            const temperature = new THREE.Mesh(tempGeometry, tempMaterial);
            temperature.position.set(positions[3].x, positions[3].y, positions[3].z);
            temperature.userData = {
                isInteractive: true,
                metricName: 'Temperature',
                metricValue: tempValue,
                metricUnit: '°C',
                highlightColor: 0x555555,
                autoRotate: true
            };

            metrics.push(temperature);
        }

        // Oxygen Saturation - Octahedron
        if (healthData.oxygenSaturation) {
            const oxygenValue = parseInt(healthData.oxygenSaturation);
            const normalizedOxygen = oxygenValue / 100; // Normalize to 0-1 range

            const oxygenGeometry = new THREE.OctahedronGeometry(1, 0);
            const oxygenMaterial = new THREE.MeshPhongMaterial({
                color: 0x1abc9c,
                emissive: 0x000000,
                shininess: 100,
                transparent: true,
                opacity: 0.5 + normalizedOxygen * 0.5 // Transparency based on value
            });

            const oxygenSaturation = new THREE.Mesh(oxygenGeometry, oxygenMaterial);
            oxygenSaturation.position.set(positions[4].x, positions[4].y, positions[4].z);
            oxygenSaturation.userData = {
                isInteractive: true,
                metricName: 'Oxygen Saturation',
                metricValue: oxygenValue,
                metricUnit: '%',
                highlightColor: 0x555555,
                autoRotate: true
            };

            metrics.push(oxygenSaturation);
        }

        // Create connecting lines between metrics
        const lineMaterial = new THREE.LineBasicMaterial({
            color: 0x00BCD4,
            transparent: true,
            opacity: 0.3
        });

        for (let i = 0; i < positions.length - 1; i++) {
            const lineGeometry = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(positions[i].x, positions[i].y, positions[i].z),
                new THREE.Vector3(positions[i+1].x, positions[i+1].y, positions[i+1].z)
            ]);

            const line = new THREE.Line(lineGeometry, lineMaterial);
            metrics.push(line);
        }

        return metrics;
    }

    // Update dashboard with new data
    function updateDashboard(newHealthData) {
        if (!dashboardVisualization) {
            console.error('Dashboard not initialized');
            return;
        }

        // Dispose old metrics
        dashboardVisualization.metrics.forEach(metric => {
            dashboardVisualization.scene.remove(metric);
            if (metric.geometry) metric.geometry.dispose();
            if (metric.material) metric.material.dispose();
        });

        // Create new metrics with updated data
        const newMetrics = create3DMetrics(newHealthData);
        newMetrics.forEach(metric => dashboardVisualization.scene.add(metric));

        // Update metrics reference
        dashboardVisualization.metrics = newMetrics;
    }

    // Dispose dashboard
    function disposeDashboard() {
        if (dashboardVisualization) {
            dashboardVisualization.dispose();
            dashboardVisualization = null;
        }
    }

    // Public API
    window.Dashboard3D = {
        init: initDashboard,
        update: updateDashboard,
        dispose: disposeDashboard
    };
})();
