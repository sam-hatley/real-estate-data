# Full Setup Guide

## 1. Prerequisites

This project was developed using Google Cloud Computing Services (GCP) and Prefect Cloud. It assumes your local environment is either Debian or Windows 11 with Debian using WSL2.

You will need to have the following accounts (Free or trial versions will work):
1. [Google Cloud Computing Services](https://cloud.google.com/)
2. [Prefect Cloud](https://app.prefect.cloud/auth/login)
3. [DBT Cloud](https://www.getdbt.com/signup/)
4. [Github](https://github.com/)

Within GCP, you will need to have a project, and a service account which includes the following permissions:
- Compute Engine default service account
- BigQuery Admin
- Storage Admin
- Storage Object Admin

If you are setting up from scratch, create a new service account and save the JSON keyfile.

Finally, on Github, fork this repository into your own account.

## 2. VM Setup

This will include some account parameters which simplify interoperability with [Visual Studio Code](https://code.visualstudio.com/). If not using Visual Studio, you may skip instructions marked with a "`*`".

### Make and Import SSH Keys to GCP*

1. In your local environment, generate a new SSH key with the below. The choice to provide a passphrase is optional, but make sure you can remember the passphrase if you use one- you will need it every time you log in to the VM.
```sh
cd ~/.ssh && \
ssh-keygen -t rsa -f gpc -C $USER -b 2048
```

2. From Google Cloud's Navigation Menu, navigate to Compute > Compute Engine > Settings > Metadata. The link to this page will be along the lines of `https://console.cloud.google.com/compute/metadata?project=<project-name>`. From within this menu, go to the "SSH KEYS" tab, select "Edit" at the top of the page, and click "ADD ITEM".

3. From the same local environment in step 1, display the public key:
```sh
cd ~/.ssh && \
cat gpc.pub
```

4. Copy the public key into the "ADD ITEM" box from step 2, and press "SAVE".

### Create a VM Instance

1. From the GCP Navigation Menu, navigate to Compute > Compute Engine > VM instances, and select "CREATE INSTANCE" at the top of the page.
2. Select a name, region, and zone that works best/is nearest to you. Make a note of the region, as we will deploy all resources into that region.
3. Choose a series and machine type that best suits you: I would recommend using e2-medium or larger. This project was mostly completed on an e2-standard-2.
4. Ensure that the Boot disk has a size of at least 64 GB and a Debian GNU/Linux 11 (bullseye) image.
5. Select "CREATE" at the bottom of the screen.
6. Return to the VM instances page, find the newly created VM and select "Start / Resume" from the three-dot menu to the right. Make a note of the machine's external IP address, as we will need this for the next section.

### Log in within VSCode*

1. From within VSCode, navigate to "Extensions" and ensure "Remote Explorer" is installed.
2. Select the Remote Explorer extension, and select the drop-down window from within the plugin window. Select "Remote"
3. If using WSL, copy the key from `~/.ssh` within your WSL environment to your Windows SSH folder, usually found at `C:\Users\<username>\.ssh`.
4. Click the gear at the right of SSH, and select a configuration file. Update the configuration file to include the details below.

```
Host real-estate-instance
    HostName <VM IP address>
    User <username>
    IdentityFile "<private ssh key location>"
```

5. If necessary, hit "Refresh" from within remote explorer, then select the instance, and connect. If you have provided one, you will be prompted for your passphrase.

### Update and Install Dependencies

1. In the VM, run the following code:

```sh
sudo apt update && sudo apt upgrade -y; \
sudo apt install wget gnupg software-properties-common
```

[Install Anaconda](https://docs.anaconda.com/anaconda/install/linux/#installation):
```sh
cd /tmp/; \
wget https://repo.anaconda.com/archive/Anaconda3-2022.10-Linux-x86_64.sh && \
bash Anaconda3-2022.10-Linux-x86_64.sh && \
rm Anaconda3-2022.10-Linux-x86_64.sh && \
source ~/.bashrc
```

[Install Terraform](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli#install-terraform):
```sh
wget -O- https://apt.releases.hashicorp.com/gpg | \
gpg --dearmor | \
sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg
```

```sh
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
sudo tee /etc/apt/sources.list.d/hashicorp.list
```

```sh
sudo apt update && \
sudo apt install terraform
```

2. Follow [this guide](https://docs.github.com/en/get-started/quickstart/set-up-git) to set up git
3. Download this repository with `cd ~ && git clone https://github.com/<your-username>/real-estate-data`
4. Navigate to the repo and run `pip install -r requirements.txt`.

## 3. Cloud Services Setup

### Terraform Setup and Services Deploy

1. Within your VM, navigate to `~/real-estate-data` and edit the file "variables.tf". The variables in the below must be updated to your personal values for region and project name:

```
variable "project" {
  description = "real-estate-data"
  default = "<Your Project ID>"
}

variable "region" {
  description = "Region for GCP resources. Choose as per your location: https://cloud.google.com/about/locations"
  default = "<Your Region>"
  type = string
}
```

2. In order, run `terraform init`, `terraform validate` to check if the configuration provided is valid, and `terraform apply` if no errors are present. This should create a data lake within Google Cloud Storage and two separate tables within BigQuery to handle HMLR and RightMove data- for this guide, only RightMove Data is relevant.

### Prefect Setup

1. Follow the [instructions here](https://discourse.prefect.io/t/how-to-run-a-prefect-2-agent-as-a-systemd-service-on-linux/1450#installing-prefect-3) from "If you are connecting to Prefect Cloud" to setup a Prefect agent locally. 
>**Important Note**: if you are using an anaconda environment, the directory will be something like `/home/{user}/anaconda3/bin/prefect`, not the dir specified in the instructions.
2. To check if everything is running correctly, run `systemctl --type=service | grep prefect` to check if `prefect-agent.service` is running.
3. If you do not have a JSON GCP service key available, from within GCP Console, navigate to IAM & Admin > Service Accounts, select your service account for the project, and create a new key. Save the produced JSON locally.
3. From within [Prefect Cloud](https://app.prefect.cloud/), navigate to "Blocks" and hit the "+" symbol. Add a "GCP Credentials" block with the block name "real-estate-data". Paste the contents of the JSON keyfile into "Service Account Info", then click "Create"
4. Add a "GCS Bucket" block with the block name "real-estate-data". Use the name of your GCS Bucket, which should be something along the lines of `data_lake_<your-project-name>`. Use the credentials provided included in step 3.
5. Build and apply the deployment using the below in the terminal:
```sh 
prefect deployment build ~/real-estate-data/parameterized.py:main -n rm_scrape --cron "0 22 * * *" -a
```
6. By default, the script should be in "test" mode, which scrapes only one page of results. Navigate to Prefect Cloud > Deployments and perform a quick run of the deployment to ensure that it functions. Once you are satisfied, navigate to the Parameters tab, click the drop-down menu, and edit the `is_testrun` parameter to `FALSE`.
> **Important Note**: Do your test runs with the `is_testrun` parameter set to `TRUE`: the ingestion script is *aggressively* rate-limited, and a full run may take well over an hour to complete.
>
>Similarly, for the script to continue working as intended, it is *essential* that it is rate-limited: too many requests in too short a time will see your IP address blocked, and frankly, isn't a very nice thing to do.
7. From the GCP Console, navigate to Storage > Cloud Storage > Buckets > data_lake_<your-project> to confirm that the `rm_data/london_daily/` directory has been created. You should have at least one parquet file within. Click on it and make a note of the `gs://` file location for the next section.

### BigQuery setup

1. In the GCP Console, navigate to Bigquery and select the "+" to open a new tab. Run the below SQL command to create an external table. Ensure that you replace `<your-project-name>` with the name of your project. In `uris`, the link should match the `gs://` address you copied in the above section.

```sql
CREATE OR REPLACE EXTERNAL TABLE <your-project-name>.rm_data.all_london_daily_external
OPTIONS (
  format = 'PARQUET',
  uris = ['gs://data_lake_<your-project-name>/rm_data/london_daily/*.parquet']
);
```

### DBT Setup

1. Ensure that [schema.yml](/dbt/models/staging/schema.yml) includes your database name on line 5:
```yml
sources:
    - name: staging
      database: <your-database-name>
      schema: rm_data
```
2. From [DBT Cloud](https://cloud.getdbt.com/), setup a new project with the name "real-estate-data". In Advanced Settings, the project subdirectory should be `dbt/`.
3. In "Configure your environment":
    - Upload your Service Account JSON keyfile where prompted
    - Paste the region you've added in [variables.tf](variables.tf) to "Location" under "Optional Settings"
    - In Add repository from, select "Github" and follow the instructions to link this project to your Github account.
4. From within DBT, select "Deploy > Environments" and create a Deployment Environment. Under "Deployment Credentials > Dataset" enter `rm_data`.
5. Select the deployment environment you just created, and create a job. Give it a Job Name, and set it to run on a chron schedule of `0 5 * * *`, or any other time at least three hours from the [Prefect deployment's start](#prefect-setup).
6. Select the job and click "Run Now" to ensure the model is working without error and generate your intial tables.

### Looker Studio Setup

1. In your browser, navigate to [Looker Studio](https://lookerstudio.google.com/) and click the "Create" button at top left to create a Data Source.
2. Under Google Connectors, select "BigQuery", and authorize your account
3. Navigate to the rm_data dataset and select a table to build a report with, and build your report.
