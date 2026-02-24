import unittest
from backend.kernel.simulation_kernel import SimulationKernel

class TestDeterminism(unittest.TestCase):
    def test_determinism(self):
        # Run 1
        kernel1 = SimulationKernel()
        kernel1.initialize(seed=42)
        for _ in range(50):
            kernel1.run_tick()

        state1 = kernel1.get_state()

        # Run 2
        kernel2 = SimulationKernel()
        kernel2.initialize(seed=42)
        for _ in range(50):
            kernel2.run_tick()

        state2 = kernel2.get_state()

        # Verify vehicles are identical
        self.assertEqual(len(state1.vehicles), len(state2.vehicles))
        for i in range(len(state1.vehicles)):
            v1 = state1.vehicles[i]
            v2 = state2.vehicles[i]
            self.assertEqual(v1.id, v2.id)
            self.assertEqual(v1.position, v2.position)
            self.assertEqual(v1.speed, v2.speed)

        # Verify signals are identical
        # GridState.intersections is a list now
        self.assertEqual(len(state1.intersections), len(state2.intersections))
        # Sort by ID to ensure order matches
        int1 = sorted(state1.intersections, key=lambda x: x.id)
        int2 = sorted(state2.intersections, key=lambda x: x.id)

        for i in range(len(int1)):
            self.assertEqual(int1[i].id, int2[i].id)
            self.assertEqual(int1[i].nsSignal, int2[i].nsSignal)
            self.assertEqual(int1[i].timer, int2[i].timer)

    def test_different_seeds(self):
        kernel1 = SimulationKernel()
        kernel1.initialize(seed=42)

        kernel2 = SimulationKernel()
        kernel2.initialize(seed=999)

        # Run enough ticks to likely diverge
        for _ in range(50):
            kernel1.run_tick()
            kernel2.run_tick()

        # Should be different
        state1 = kernel1.get_state()
        state2 = kernel2.get_state()

        diverged = False
        if len(state1.vehicles) != len(state2.vehicles):
            diverged = True
        else:
            for i in range(len(state1.vehicles)):
                if state1.vehicles[i].position != state2.vehicles[i].position:
                    diverged = True
                    break

        self.assertTrue(diverged, "Different seeds should produce different states")

if __name__ == '__main__':
    unittest.main()
