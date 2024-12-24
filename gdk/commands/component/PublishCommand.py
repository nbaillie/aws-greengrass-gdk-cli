import logging
from pathlib import Path
import yaml
import json
from gdk.common import diff_utils
from gdk.commands.component.transformer.PublishRecipeTransformer import PublishRecipeTransformer

import gdk.commands.component.component as component
import gdk.common.utils as utils
from gdk.aws_clients.Greengrassv2Client import Greengrassv2Client
from gdk.aws_clients.S3Client import S3Client
from gdk.commands.Command import Command
from gdk.commands.component.config.ComponentPublishConfiguration import ComponentPublishConfiguration
from gdk.common.CaseInsensitive import CaseInsensitiveRecipeFile


class PublishCommand(Command):
    def __init__(self, command_args) -> None:
        super().__init__(command_args, "publish")

        self.project_config = ComponentPublishConfiguration(command_args)
        self.s3_client = S3Client(self.project_config.region)
        self.greengrass_client = Greengrassv2Client(self.project_config.region)

    def run(self):
        try:
            self.try_build()
            self._publish_component_version(self.project_config.component_name, self.project_config.component_version)
        except Exception:
            logging.error(
                "Failed to publish a new version '%s' of the component '%s'.",
                self.project_config.component_version,
                self.project_config.component_name,
            )
            raise

    def _check_for_changes(self):
        logging.info(f"Checking for changes in the component: {self.project_config.component_name}")

        options = self.project_config.options
        only_on_change = options.get("only_on_change", [])

        if only_on_change:
            latest_published_recipe = self._get_latest_published_recipe()
            if not latest_published_recipe:
                logging.info(f"No published recipe found for the component: {self.project_config.component_name}")
                return True

            if "RECIPE" in only_on_change:
                logging.info("Checking for changes in the RECIPE.")
                if self._diff_recipe(latest_published_recipe):
                    return True

            if "ARTIFACTS" in only_on_change:
                logging.info("Checking for changes in the ARTIFACTS.")
                if self._diff_artifacts(latest_published_recipe):
                    return True

            logging.info(f"No changes in the component: {self.project_config.component_name}")
            return False

        else:
            logging.info(f"Publishing regardless of RECIPE or ARTIFACT diff: {self.project_config.component_name}")
            return True

    def _diff_artifacts(self, latest_published_recipe):
        build_artifacts = list(self.project_config.gg_build_component_artifacts_dir.iterdir())

        for build_artifact in build_artifacts:
            artifact_found_in_latest_manifest = False
            for latest_p_manifest in latest_published_recipe.get("Manifests", []):
                for latest_p_artifact in latest_p_manifest.get("Artifacts", []):
                    if latest_p_artifact.get("URI", latest_p_artifact.get("Uri")).split("/")[-1] == build_artifact.name:
                        artifact_found_in_latest_manifest = True
                        if latest_p_artifact.get("Digest", None) != utils.artifact_encoded_hash(build_artifact):
                            logging.info(f"Changes found in the artifact: {build_artifact}")
                            return True

            if not artifact_found_in_latest_manifest:
                logging.info("Could not find find the published artifact: {build_artifact}")
                return True

        logging.info("No Changes found in the artifacts")
        return False

    def _check_recipe_structure(self, recipe, latest_published_recipe):
        """Check for structural changes in the recipe."""
        diff = diff_utils.deep_diff(
            latest_published_recipe,
            recipe,
            exclude_paths=[
                "root['Lifecycle']",
                "root['ComponentVersion']",
                "root['ComponentType']"
            ],
            exclude_regex_paths=[
                "^root\['Manifests'\]\[.+\]\['Artifacts'\]\[.+\]",  # noqa: W605
                "^root\['Manifests'\]\[.+\]\['Artifacts'\]"         # noqa: W605
            ]
        )

        logging.info(f"Recipe diff: {json.dumps(diff, indent=4)}")

        if "dictionary_item_added" in diff.keys() and len(diff['dictionary_item_removed']) > 0:
            logging.info(f"Changes found: dictionary_item_added: {item}")
            return True

        if "dictionary_item_removed" in diff.keys() and len(diff['dictionary_item_removed']) > 0:
            logging.info("Changes found: dictionary_item_removed")
            return True

        if "values_changed" in diff.keys() and len(diff['values_changed'].keys()) > 0:
            logging.info(f"Changes found: values_changed: {json.dumps(diff['values_changed'], indent=2)}")
            return True

        return False

    def _check_manifests(self, recipe, latest_published_recipe):
        """Check for changes in manifests and artifacts."""
        manifests = recipe.get("Manifests", [])
        latest_manifests = latest_published_recipe.get("Manifests")

        if len(manifests) != len(latest_manifests):
            logging.info("Changes found in the number of defined Manifests")
            return True

        for idm, manifest in enumerate(manifests):
            if self._check_artifacts(manifest, latest_manifests[idm]):
                return True

        return False

    def _check_artifacts(self, manifest, latest_manifest):
        """Check for changes in artifacts."""
        artifacts = manifest.get("Artifacts", [])
        latest_artifacts = latest_manifest.get("Artifacts", [])

        if len(artifacts) != len(latest_artifacts):
            logging.info("Changes found in the number of defined Artifacts")
            return True

        if not artifacts:
            return False

        for ida, artifact in enumerate(artifacts):
            if self._check_single_artifact(artifact, latest_artifacts[ida]):
                return True

        return False

    def _check_single_artifact(self, artifact, latest_artifact):
        """Check for changes in a single artifact."""
        recipe_uri = artifact.get("URI", artifact.get("Uri"))
        recipe_unarchive = artifact.get("Unarchive", "")

        latest_uri = latest_artifact.get("URI", latest_artifact.get("Uri"))
        latest_unarchive = latest_artifact.get("Unarchive", "")
        latest_published_version = self.project_config.latest_published_component_version

        # # Check URI changes
        recipe_version = self.project_config.component_version
        # latest_version = self.latest_version or ''
        if recipe_uri.replace(recipe_version, '<VERSION>') != latest_uri.replace(latest_published_version, '<VERSION>'):
            logging.info(f"Changes found: Artifact URI: local: {recipe_uri}")
            logging.info(f"Changes found: Artifact URI: in gg: {latest_uri}")
            return True

        # # Check unarchive changes
        if recipe_unarchive != latest_unarchive:
            logging.info(f"Changes found: Artifact Unarchive: local: {recipe_unarchive}")
            logging.info(f"Changes found: Artifact Unarchive: in gg: {latest_unarchive}")
            return True

        return False

    def _log_recipe_comparison(self, recipe, latest_published_recipe):
        """Log the recipe comparison details."""
        logging.debug(f"Recipe Local: {json.dumps(recipe,indent=2)}")
        logging.debug(f"Recipe in Greengrass: {json.dumps(latest_published_recipe,indent=2)}")

    def _diff_recipe(self, latest_published_recipe):
        recipe = self._get_recipe().to_dict()

        self._log_recipe_comparison(recipe, latest_published_recipe)

        if not latest_published_recipe:
            logging.info(f"No published recipe found for the component to check against: {self.project_config.component_name}")
            return True

        if self._check_recipe_structure(recipe, latest_published_recipe):
            return True

        if self._check_manifests(recipe, latest_published_recipe):
            return True

        logging.info("No Changes found in the recipe")
        return False

    def _get_latest_published_recipe(self):
        if self.project_config.latest_published_component_version:
            component = f"components:{self.project_config.component_name}"
            version = f"versions:{self.project_config.latest_published_component_version}"
            component_with_version = f"{component}:{version}"
            arn = f"arn:aws:greengrass:{self.project_config.region}:{self.project_config.account_num}:{component_with_version}"
            return yaml.safe_load(self.greengrass_client.get_component(arn).decode('utf8'))
        else:
            return None

    def _get_recipe(self):
        recipe_path = Path(self.project_config.publish_recipe_file)
        return CaseInsensitiveRecipeFile().read(recipe_path)

    def try_build(self):
        # TODO: This method should just warn and proceed. It should not build the component.
        component_name = self.project_config.component_name
        logging.debug("Checking if the component '%s' is built.", component_name)
        if not utils.dir_exists(self.project_config.gg_build_component_artifacts_dir):
            logging.warning(
                "The component '%s' is not built.\nSo, building the component before publishing it.", component_name
            )
            component.build({})

    def _publish_component_version(self, component_name, component_version):
        logging.info("Publishing the component '%s' with the given project configuration.", component_name)

        logging.info("Transform the component recipe %s-%s.", component_name, component_version)
        PublishRecipeTransformer(self.project_config).transform()
        if self._check_for_changes():

            logging.info("Uploading the component built artifacts to s3 bucket.")
            self.upload_artifacts_s3()

            logging.info("Creating a new greengrass component version %s-%s.", component_name, component_version)
            self.greengrass_client.create_gg_component(self.project_config.publish_recipe_file)
            logging.info("Latest published version is now: %s-%s", component_name, self.project_config.component_version)
        else:
            logging.info("No changes found in the component. Skipping the publish step.")
            logging.info(
                "Latest published version remains: %s-%s",
                component_name,
                self.project_config.latest_published_component_version
            )

    def upload_artifacts_s3(self) -> None:
        """
        Uploads all the artifacts from component artifacts build folder to s3 bucket.

        Raises an exception when the request is not successful.
        """
        _bucket = self.project_config.bucket

        build_component_artifacts = list(self.project_config.gg_build_component_artifacts_dir.iterdir())

        if not build_component_artifacts:
            logging.info("No artifacts found in the component build folder. Skipping the artifact upload step")
            return

        logging.info(
            (
                "Uploading component artifacts to S3 bucket: %s. If this is your first time using this bucket, add the"
                " 's3:GetObject' permission to each core device's token exchange role to allow it to download the component"
                " artifacts. For more information, see %s."
            ),
            _bucket,
            utils.doc_link_device_role,
        )

        self.s3_client.create_bucket(_bucket)

        component_name = self.project_config.component_name
        component_version = self.project_config.component_version
        options = self.project_config.options
        s3_upload_file_args = options.get("file_upload_args", {})

        for artifact in build_component_artifacts:
            s3_file_path = f"{component_name}/{component_version}/{artifact.name}"
            logging.debug("Uploading artifact '%s' to the bucket '%s'.", artifact.resolve(), _bucket)
            self.s3_client.upload_artifact(artifact, _bucket, s3_file_path, s3_upload_file_args)
