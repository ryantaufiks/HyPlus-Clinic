/**
 * Three.js Initialization for AIVIN
 * This script initializes Three.js scene, camera, and renderer
 */

let scene, camera, renderer, clock;
let container;
let animations = [];

// Initialize Three.js scene
function initThreeJS() {
    // Check if Three.js is loaded
    if (typeof THREE === 'undefined') {
        console.error('Three.js not loaded');
        return false;
    }

    // Create container if not exists
    container = document.createElement('div');
    container.id = 'threejs-container';
    container.style.position = 'fixed';
    container.style.top = '0';
    container.style.left = '0';
    container.style.width = '100%';
    container.style.height = '100%';
    container.style.zIndex = '-1';
    container.style.pointerEvents = 'none';
    document.body.insertBefore(container, document.body.firstChild);

    // Create scene
    scene = new THREE.Scene();

    // Create camera
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.z = 5;

    // Create renderer
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setClearColor(0x000000, 0); // Transparent background
    container.appendChild(renderer.domElement);

    // Create clock for animations
    clock = new THREE.Clock();

    // Handle window resize
    window.addEventListener('resize', onWindowResize, false);

    // Start animation loop
    animate();

    return true;
}

// Handle window resize
function onWindowResize() {
    if (!camera || !renderer) return;

    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}

// Animation loop
function animate() {
    requestAnimationFrame(animate);

    const elapsedTime = clock.getElapsedTime();

    // Update all animations
    animations.forEach(animation => {
        if (animation && typeof animation.update === 'function') {
            animation.update(elapsedTime);
        }
    });

    renderer.render(scene, camera);
}

// Add animation to the loop
function addAnimation(animation) {
    if (animation && typeof animation.update === 'function') {
        animations.push(animation);
    }
}

// Remove animation from the loop
function removeAnimation(animation) {
    const index = animations.indexOf(animation);
    if (index > -1) {
        animations.splice(index, 1);
    }
}

// Clean up Three.js resources
function disposeThreeJS() {
    window.removeEventListener('resize', onWindowResize, false);

    animations = [];

    if (renderer) {
        renderer.dispose();
        container.removeChild(renderer.domElement);
    }

    if (container && container.parentNode) {
        container.parentNode.removeChild(container);
    }

    scene = null;
    camera = null;
    renderer = null;
    clock = null;
    container = null;
}

// Export functions for other scripts to use
window.ThreeJSUtils = {
    init: initThreeJS,
    addAnimation: addAnimation,
    removeAnimation: removeAnimation,
    getScene: () => scene,
    getCamera: () => camera,
    getRenderer: () => renderer,
    getClock: () => clock,
    dispose: disposeThreeJS
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initThreeJS();
});
