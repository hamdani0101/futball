/* Reusable football pitch component (framework-free).
 *
 * Coordinate system: StatsBomb-style 0-120 (length) x 0-80 (width),
 * the single source of truth across collection UI and analytics.
 * Attack is left-to-right by default; set `flipped: true` to mirror
 * for second-half orientation without changing stored coordinates.
 *
 * Usage:
 *   const pitch = FutballPitch.create(svgEl, markersEl);
 *   const pos = pitch.toCoords(clientX, clientY); // {x, y}
 *   pitch.markShot(x, y); pitch.markPass(x1, y1, x2, y2); pitch.clear();
 */
(function (global) {
    'use strict';

    var SVG_NS = 'http://www.w3.org/2000/svg';

    var COLORS = {
        shot: '#ef4444',
        goal: '#f59e0b',
        passStart: '#38bdf8',
        passEnd: '#0ea5e9',
        generic: '#a855f7',
        save: '#0ea5e9',
    };

    function FutballPitch(svgEl, markersEl, options) {
        this.svg = svgEl;
        this.markers = markersEl;
        this.options = options || {};
    }

    FutballPitch.prototype.toCoords = function (clientX, clientY) {
        var rect = this.svg.getBoundingClientRect();
        var x = ((clientX - rect.left) / rect.width) * 120;
        var y = ((clientY - rect.top) / rect.height) * 80;
        var pos = {
            x: Math.max(0, Math.min(120, x)),
            y: Math.max(0, Math.min(80, y)),
        };
        if (this.options.flipped) {
            pos.x = 120 - pos.x;
            pos.y = 80 - pos.y;
        }
        return pos;
    };

    FutballPitch.prototype.clear = function () {
        this.markers.innerHTML = '';
        this._registry = {};
    };

    // Id-tracked markers so the timeline can highlight/select/remove one
    // event marker without redrawing the whole layer.
    FutballPitch.prototype.addMarker = function (id, x, y, color, label) {
        this.removeMarker(id);
        var g = document.createElementNS(SVG_NS, 'g');
        g.setAttribute('data-marker-id', id);
        var circle = document.createElementNS(SVG_NS, 'circle');
        circle.setAttribute('cx', x);
        circle.setAttribute('cy', y);
        circle.setAttribute('r', 2.2);
        circle.setAttribute('fill', color);
        circle.setAttribute('stroke', 'white');
        circle.setAttribute('stroke-width', '0.8');
        circle.setAttribute('class', 'pitch-marker-dot');
        g.appendChild(circle);
        if (label) {
            var text = document.createElementNS(SVG_NS, 'text');
            text.setAttribute('x', x + 3);
            text.setAttribute('y', y - 2);
            text.setAttribute('fill', 'white');
            text.setAttribute('font-size', '3');
            text.setAttribute('font-weight', 'bold');
            text.textContent = label;
            g.appendChild(text);
        }
        this.markers.appendChild(g);
        (this._registry = this._registry || {})[id] = g;
        return g;
    };

    FutballPitch.prototype.removeMarker = function (id) {
        var existing = (this._registry || {})[id];
        if (existing && existing.parentNode) existing.parentNode.removeChild(existing);
        if (this._registry) delete this._registry[id];
    };

    FutballPitch.prototype.highlightMarker = function (id) {
        var nodes = this.markers.querySelectorAll('g[data-marker-id]');
        for (var i = 0; i < nodes.length; i++) {
            var dot = nodes[i].querySelector('.pitch-marker-dot');
            if (!dot) continue;
            if (String(nodes[i].getAttribute('data-marker-id')) === String(id)) {
                dot.setAttribute('r', 3.4);
                dot.setAttribute('stroke', '#fbbf24');
                dot.setAttribute('stroke-width', '1.4');
            } else {
                dot.setAttribute('r', 2.2);
                dot.setAttribute('stroke', 'white');
                dot.setAttribute('stroke-width', '0.8');
            }
        }
    };

    FutballPitch.prototype._dot = function (x, y, color, label) {
        var circle = document.createElementNS(SVG_NS, 'circle');
        circle.setAttribute('cx', x);
        circle.setAttribute('cy', y);
        circle.setAttribute('r', 2.2);
        circle.setAttribute('fill', color);
        circle.setAttribute('stroke', 'white');
        circle.setAttribute('stroke-width', '0.8');
        this.markers.appendChild(circle);
        if (label) {
            var text = document.createElementNS(SVG_NS, 'text');
            text.setAttribute('x', x + 3);
            text.setAttribute('y', y - 2);
            text.setAttribute('fill', 'white');
            text.setAttribute('font-size', '3');
            text.setAttribute('font-weight', 'bold');
            text.textContent = label;
            this.markers.appendChild(text);
        }
    };

    FutballPitch.prototype.markShot = function (x, y) {
        this.clear();
        this._dot(x, y, COLORS.shot);
    };

    FutballPitch.prototype.markGoal = function (x, y) {
        this.clear();
        this._dot(x, y, COLORS.goal, 'GOAL');
    };

    FutballPitch.prototype.markGeneric = function (x, y, color) {
        this.clear();
        this._dot(x, y, color || COLORS.generic);
    };

    FutballPitch.prototype.markPassStart = function (x, y) {
        this.clear();
        this._dot(x, y, COLORS.passStart, 'Start');
    };

    FutballPitch.prototype.markPass = function (x1, y1, x2, y2) {
        this._dot(x2, y2, COLORS.passEnd, 'End');
        var line = document.createElementNS(SVG_NS, 'line');
        line.setAttribute('x1', x1);
        line.setAttribute('y1', y1);
        line.setAttribute('x2', x2);
        line.setAttribute('y2', y2);
        line.setAttribute('stroke', COLORS.passStart);
        line.setAttribute('stroke-width', '1.5');
        line.setAttribute('stroke-dasharray', '2 1.5');
        this.markers.appendChild(line);
    };

    FutballPitch.create = function (svgEl, markersEl, options) {
        return new FutballPitch(svgEl, markersEl, options);
    };

    FutballPitch.COLORS = COLORS;

    global.FutballPitch = FutballPitch;
})(window);
