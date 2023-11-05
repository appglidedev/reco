import logging
from datetime import datetime
import streamlit as st
import pandas as pd
import csv
from io import StringIO

logger = logging.getLogger(__name__)

from config import ai_header_columns, ca_header_columns, rebates
from exceptions import InvalidFileException, TypeConversionException, FileParseException

def check_for_header_row(uploaded_file, header_columns):
    data = csv.reader(uploaded_file)
    # Remove '\ufeff BOM in any header columns
    data = [[c.replace('\ufeff','') for c in row] for row in data]
    for idx, row in enumerate(data):
        # Retain only letters in row and convert to lower
        row = ["".join(filter(str.isalpha, c)).lower() for c in row]
        # Check if row contains the mandatory columns
        if all(col in row for col in [k for k,v in header_columns.items() if v['mandatory']]):
            return idx
    return None

def process_uploaded_file(uploaded_file:StringIO, header_row_num:int, header_columns:dict) -> pd.DataFrame:
    """
    Process uploaded file and return a pandas data frame
    """
    # Convert into pandas data frame at the header row
    try:
        df = pd.read_csv(uploaded_file, skiprows = header_row_num)
    except:
        raise FileParseException("Error parsing CSV file")
    # Drop any unnamed columns created during csv read
    df = df.loc[:, ~df.columns.str.contains('^unnamed')]
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    # Drop NaN rows
    df.dropna(inplace = True, ignore_index = True)
    # Rename columns to remove spaces and convert to lower case
    new_column_names = {key:''.join(filter(str.isalnum, key)).lower() for key in df.columns}
    df = df.rename(new_column_names, axis = 1)
    # Keep only mandatory columns
    df = df[[k for k,v in header_columns.items() if v['mandatory']]]
    # Convert columns to specified data types
    for column in df.columns:
        print("Checking column", column)
        # If the column is expected to be datetime, use parser to convert
        if header_columns[column]['type'] == datetime:
            try:
                df[column] = pd.to_datetime(df[column])
            except:
                raise TypeConversionException("Error converting column {} to datetime".format(column))
        # For other expected data types, convert column to that type
        elif df[column].dtype != header_columns[column]['type']:
            try:
                df[column] = df[column].astype(header_columns[column]['type'])
            except:
                raise TypeConversionException("Error converting column {} to {}".format(column, ai_header_columns[column]['type']))
    return df

def calculate_rebate(df:pd.DataFrame) -> pd.DataFrame:
    """
    Calculate rebate values for reconciled and merged dataframe
    from AI and CA data
    """
    rebate_row_values = []
    for index, row in df.iterrows():
        company_name = row['company']
        rebate_percentage = 0
        for key in rebates:
            #  If company is JiffyLube check rebate by location (US/CA)
            if key in company_name:
                if key == "jiffylube":
                    if row['country'] == "us":
                        rebate_percentage = rebates[key]["us"]
                    if row['country'] == "ca":
                        rebate_percentage = rebates[key]["ca"]
                else:
                    rebate_percentage = rebates[key]["all"]
        shop_rebate = - rebate_percentage * row['subtotal']
        rebate_row_values.append(shop_rebate)
    df['calculatedrebate'] = rebate_row_values
    df['amountnetrebate'] = df['payableamount'] - df['calculatedrebate']
    return df

def convert_df_to_csv(df):
   return df.to_csv(index=False).encode('utf-8')
            

def main():
    """
    Reconciliation app
    """
    if 'ai_uploaded' not in st.session_state:
        st.session_state.ai_uploaded = False

    if 'ca_uploaded' not in st.session_state:
        st.session_state.ca_uploaded = False

    if 'ai_data' not in st.session_state:
        st.session_state.ai_data = None

    if 'ca_data' not in st.session_state:
        st.session_state.ca_data = None
    
    st.title("Car Advise Transaction Reconciliation")

    # Process uploaded AutoIntegrate file
    with st.expander("Upload Auto Integrate data file"):
        uploaded_file = st.file_uploader("Upload AI file", type=["csv"])
        if uploaded_file is not None:
            # Process file
            with StringIO(uploaded_file.getvalue().decode("utf-8")) as ai_file:
                print(type(ai_file))
                header_row = check_for_header_row(ai_file, ai_header_columns)
            if not st.session_state.ai_uploaded:
                with st.spinner("Processing..."):
                    if header_row is None:
                        raise InvalidFileException("Invalid Auto Integrate file")
                    else:
                        ai_data = process_uploaded_file(uploaded_file, header_row, ai_header_columns)
                        if ai_data is None:
                            st.error("Error processing AI Data")
                        else:
                            st.session_state.ai_data = ai_data
                            st.success("AI data processed successfully")
                            st.session_state.ai_uploaded = True
            else:
                st.success("AI data uploaded successfully")
    
    # Process uploaded CarAdvise file
    with st.expander("Upload Car Advise data file"):
        uploaded_file = st.file_uploader("Upload CA file", type=["csv"])
        if uploaded_file is not None:
            # Process file
            with StringIO(uploaded_file.getvalue().decode("utf-8")) as ca_file:
                print(type(ca_file))
                header_row = check_for_header_row(ca_file, ca_header_columns)
            if not st.session_state.ca_uploaded:
                with st.spinner("Processing..."):
                    if header_row is None:
                        raise InvalidFileException("Invalid Car Advise file")
                    else:
                        ca_data = process_uploaded_file(uploaded_file, header_row, ca_header_columns)
                        if ca_data is None:
                            st.error("Error processing CA Data")
                        else:
                            ca_data['roid'] = ca_data['aiorderid']
                            st.session_state.ca_data = ca_data
                            st.success("CA data processed successfully")
                            st.session_state.ca_uploaded = True
            else:
                st.success("CA data uploaded successfully")    
    print("Checking..")
    ai_data = st.session_state.ai_data
    ca_data = st.session_state.ca_data
    print(type(ai_data), type(ca_data))
    if isinstance(ai_data, pd.DataFrame) and isinstance(ca_data, pd.DataFrame):
        # Convert company names in CarAdvise data to lower case letters
        ca_data['company'] = ca_data['company'].str.replace('[^a-zA-Z]', '')
        ca_data['company'] = ca_data['company'].str.lower()
        merged_df = pd.merge(ai_data, ca_data, how = "inner", on = "roid")
        # calculate rebates
        df_with_rebates = calculate_rebate(merged_df)
        st.subheader("Reconciled Transactions")
        st.write(merged_df.head(5))
        merged_csv = convert_df_to_csv(merged_df)
        st.download_button(
            "Download",
            merged_csv,
            "file.csv",
            "text/csv",
            key='download-merged'
        )

        # Find rows that are in AI Data and not in CA Data
        common = ai_data.merge(ca_data,on=['roid'])
        ai_not_in_ca = ai_data[(~ai_data.roid.isin(common.roid))]
        st.subheader("Auto Integrate data rows not found in CarAdvise data")
        st.write(ai_not_in_ca.head(10))
        ai_not_in_ca_csv = convert_df_to_csv(ai_not_in_ca)
        st.download_button(
            "Download",
            ai_not_in_ca_csv,
            "file.csv",
            "text/csv",
            key='download-missing'
        )
                            
if __name__ == '__main__':
    main()