"""Receipt-owned producer and proof handoff using private host fixtures."""
from pathlib import Path

from test_lyra_current_transfer import CurrentSaveTransferTest
import lyra_current_transfer as X


class ReceiptOnlyHandoffTest(CurrentSaveTransferTest):
    def test_missing_producer_identity_refuses_before_snapshot(self):
        descriptor = self.project.read_text().replace(
            'native_save_producer_file=producer.json\n', '')
        self.project.write_text(descriptor)
        self.inputs['project'] = X.Q.bound(self.project)
        self.save['artifacts'] = self.artifacts(self.inputs)
        self.receipt.write_bytes(X.P.encoded(self.save))
        before = self.project.read_bytes()
        with self.assertRaisesRegex(ValueError, 'no native_save_producer_file'):
            self.prepare()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.candidate.exists())
        self.assertEqual(self.project.read_bytes(), before)

    def test_receipt_handoff_without_project_producer_or_proof_fields(self):
        descriptor = self.project.read_text()
        descriptor = descriptor.replace('native_save_producer_file=producer.json\n', '')
        descriptor = descriptor.replace('native_save_transfer_proof_file=transfer-proof.json\n', '')
        self.project.write_text(descriptor)
        self.inputs['project'] = X.Q.bound(self.project)
        self.save['artifacts'] = self.artifacts(self.inputs)
        self.receipt.write_bytes(X.P.encoded(self.save))
        external = self.root / 'actual-producer.json'
        external.write_bytes(self.producer_path.read_bytes())
        before = self.project.read_bytes()

        _, request = self.prepare(producer_identity=external)
        transfer, _, _ = X.verify_transfer(request, self.project, self.rom)
        self.assertIsNone(transfer['live']['enforcement_receipt'])
        self.assertEqual(transfer['live']['producer'], X.Q.bound(external))
        with self.assertRaisesRegex(ValueError, 'CURRENT_SAVE_PRODUCER_PROOF_REQUIRED'):
            X._legacy_proof_path(transfer['live'])

        original_proof = self.enforcement
        self.enforcement = self.root / 'legacy-fixture-proof.json'
        try:
            ledger, policy, _ = self.grant_fixture(request)
        finally:
            self.enforcement = original_proof
        policy.update(kind=X.NATIVE_POLICY_KIND,
                      producer_identity_sha256=transfer['live']['producer']['sha256'],
                      enforcement=dict(owner='oracle.current_builder',
                                       required_order=X.COMPILE_ORDER))
        self.write_fixture_ledger(ledger, policy)
        plan, _ = X.plan_transfer(request, self.project, self.rom,
                                  current_source_profile=self.current_profile)
        self.assertEqual(plan['enforcement_owner'], 'oracle.current_builder')
        self.assertEqual(plan['enforcement_receipt'], transfer['native_verification'])
        self.assertEqual(self.project.read_bytes(), before)
        self.assertFalse(Path(original_proof).exists())
        self.assertFalse(self.candidate.exists())
